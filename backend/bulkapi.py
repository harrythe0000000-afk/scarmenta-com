import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import io
import csv
import json
import math
import logging
import os
import re
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core import client_ip, db, get_current_user, make_tx, new_id, now_iso, require_admin, require_staff

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
INF_BASE = os.environ["INFINITY_BASE_URL"].rstrip("/")
LAUNCH_URL = INF_BASE + "/api/v1/launch.php"
DEFAULT_RATE = 95.0


_FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256(os.environ["JWT_SECRET"].encode()).digest()))
_CACHE = {"at": 0.0, "token": "", "secret": "", "cb_token": "", "source": "none"}


async def _ensure() -> None:
    if time.time() - _CACHE["at"] < 30:
        return
    doc = await db.settings.find_one({"key": "infinity_creds"}, {"_id": 0}) or {}
    if not doc.get("cb_enc"):
        cb = secrets.token_urlsafe(32)
        await db.settings.update_one({"key": "infinity_creds", "cb_enc": {"$exists": False}},
                                     {"$set": {"cb_enc": _FERNET.encrypt(cb.encode()).decode()}}, upsert=True)
        doc = await db.settings.find_one({"key": "infinity_creds"}, {"_id": 0}) or {}
    dec = lambda v: _FERNET.decrypt(v.encode()).decode() if v else ""
    try:
        token, secret = dec(doc.get("token_enc")), dec(doc.get("secret_enc"))
        _CACHE["cb_token"] = dec(doc.get("cb_enc"))
    except InvalidToken:
        logger.error("Saved BULKAPI keys cannot be decrypted (JWT_SECRET changed?); using server keys")
        token, secret = "", ""
    src = "admin panel" if token or secret else "server"
    _CACHE.update(at=time.time(), source=src,
                  token=token or os.environ.get("INFINITY_API_KEY", "").strip(),
                  secret=secret or os.environ.get("INFINITY_CLIENT_SECRET", "").strip())


def _token() -> str:
    return _CACHE["token"]


def _secret() -> bytes:
    return _CACHE["secret"].encode()


def _mask(v: str) -> str:
    return f"••••{v[-4:]}" if len(v) > 4 else ("••••" if v else "")


class LaunchError(Exception):
    def __init__(self, code: str, status: int = 0, detail: str = ""):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


def member_account(pid: str) -> str:
    return f"scm_{pid}"


async def infinity_launch(member: str, balance_inr: float, game_uid: str, return_url: str) -> dict:
    await _ensure()
    if not _token() or not _secret():
        raise LaunchError("not_configured")
    bal, ts = f"{balance_inr:.2f}", str(int(time.time()))
    sig = hmac.new(_secret(), "|".join([_token(), member, game_uid, bal, ts]).encode(), hashlib.sha256).hexdigest()
    fields = {"api_key": _token(), "user_id": member, "game_uid": game_uid, "balance": bal, "ts": ts, "sig": sig,
              "currency_code": "INR", "language": "en", "return": return_url, "redirect": "0"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5), follow_redirects=False) as c:
            r = await c.post(LAUNCH_URL, data=fields)
    except httpx.TimeoutException:
        raise LaunchError("timeout", 0, "InfinityAPI did not answer in time. Do not retry blindly; check launch history.")
    except httpx.HTTPError as e:
        raise LaunchError("connection_failed", 0, e.__class__.__name__)
    try:
        j = r.json()
    except ValueError:
        j = None
    if not isinstance(j, dict) or j.get("ok") is not True or not (200 <= r.status_code < 300):
        err = str((j or {}).get("error") or (j or {}).get("message") or "invalid_response")[:120] if isinstance(j, dict) else "invalid_response"
        logger.warning(f"Infinity launch rejected http={r.status_code} error={err} request_id={(j or {}).get('request_id') if isinstance(j, dict) else None}")
        raise LaunchError(err, r.status_code, r.text[:300])
    url = str(j.get("game_url") or "")
    if not url.startswith("https://"):
        raise LaunchError("invalid_game_url", r.status_code)
    return {"game_url": url, "request_id": j.get("request_id")}


async def enabled_providers() -> set:
    return set(await db.live_providers.distinct("name", {"enabled": True}))


async def live_rate() -> float:
    doc = await db.settings.find_one({"key": "live_casino"}, {"_id": 0}) or {}
    return float(doc.get("inr_rate") or DEFAULT_RATE)


async def player_id(user: dict) -> str:
    if user.get("bulk_player_id"):
        return user["bulk_player_id"]
    for _ in range(10):
        pid = "9" + "".join(secrets.choice("0123456789") for _ in range(9))
        try:
            r = await db.users.update_one({"id": user["id"], "bulk_player_id": {"$exists": False}}, {"$set": {"bulk_player_id": pid}})
            if r.modified_count:
                return pid
            return (await db.users.find_one({"id": user["id"]}, {"bulk_player_id": 1}))["bulk_player_id"]
        except DuplicateKeyError:
            continue
    raise HTTPException(status_code=500, detail="Could not create player ID")


# ---------- Games catalogue ----------
class GameIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    provider: str = Field(min_length=2, max_length=40)
    game_uid: str = Field(min_length=1, max_length=80)
    image_id: Optional[str] = None
    active: bool = True


class GamePatch(BaseModel):
    active: bool


FIELDS = {"_id": 0, "id": 1, "name": 1, "provider": 1, "game_uid": 1, "image_id": 1, "image_url": 1, "active": 1, "created_at": 1}


@router.get("/live/games")
async def player_games(_: dict = Depends(get_current_user)):
    rows = await db.live_games.find({"active": True, "deleted": {"$ne": True}, "provider": {"$in": list(await enabled_providers())}},
                                    FIELDS).sort("provider", 1).to_list(2000)
    return [{k: v for k, v in g.items() if k not in ("_id", "game_uid")} for g in rows]


class FavIn(BaseModel):
    favourite: bool


@router.get("/live/favourites")
async def get_favourites(user: dict = Depends(get_current_user)):
    return user.get("live_favourites", [])


@router.put("/live/favourites/{gid}")
async def set_favourite(gid: str, body: FavIn, user: dict = Depends(get_current_user)):
    if body.favourite:
        if not await db.live_games.find_one({"id": gid, "active": True, "deleted": {"$ne": True}}, {"_id": 1}):
            raise HTTPException(status_code=404, detail="Game not available")
        upd = {"$addToSet": {"live_favourites": gid}}
    else:
        upd = {"$pull": {"live_favourites": gid}}
    u = await db.users.find_one_and_update({"id": user["id"]}, upd, projection={"_id": 0, "live_favourites": 1},
                                           return_document=ReturnDocument.AFTER)
    return u.get("live_favourites", [])


@router.get("/live/recent")
async def recent_games(user: dict = Depends(get_current_user)):
    rows = await db.live_sessions.aggregate([
        {"$match": {"user_id": user["id"], "status": "launched"}},
        {"$group": {"_id": "$game_id", "last": {"$max": "$created_at"}}}, {"$sort": {"last": -1}}, {"$limit": 20}]).to_list(20)
    active = {g["id"] for g in await db.live_games.find({"id": {"$in": [r["_id"] for r in rows]}, "active": True,
                                                        "deleted": {"$ne": True}, "provider": {"$in": list(await enabled_providers())}},
                                                       {"_id": 0, "id": 1}).to_list(20)}
    return [{"id": r["_id"], "last": r["last"]} for r in rows if r["_id"] in active][:5]


@router.get("/live/popular")
async def popular_games(_: dict = Depends(get_current_user)):
    top = await db.live_rounds.aggregate([
        {"$group": {"_id": "$game_uid", "rounds": {"$sum": 1}}}, {"$sort": {"rounds": -1}}, {"$limit": 30}]).to_list(30)
    games = await db.live_games.find({"game_uid": {"$in": [t["_id"] for t in top]}, "active": True, "deleted": {"$ne": True},
                                      "provider": {"$in": list(await enabled_providers())}},
                                     {"_id": 0, "id": 1, "game_uid": 1}).to_list(30)
    ids = {g["game_uid"]: g["id"] for g in games}
    return [{"id": ids[t["_id"]], "rounds": t["rounds"]} for t in top if t["_id"] in ids][:5]


@router.get("/admin/live/games")
async def admin_games(_: dict = Depends(require_staff)):
    rows = await db.live_games.find({"deleted": {"$ne": True}}, FIELDS).sort("created_at", -1).to_list(500)
    return [{k: v for k, v in g.items() if k != "_id"} for g in rows]


@router.post("/admin/live/games")
async def add_game(body: GameIn, admin: dict = Depends(require_admin)):
    if await db.live_games.find_one({"game_uid": body.game_uid.strip(), "deleted": {"$ne": True}}):
        raise HTTPException(status_code=400, detail="A game with this game_uid already exists")
    if not await db.live_providers.find_one({"name": body.provider}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="Unknown provider. Add it in the Providers tab first.")
    doc = {"id": new_id(), **body.model_dump(), "game_uid": body.game_uid.strip(), "created_by": admin["email"],
           "created_at": now_iso(), "deleted": False}
    await db.live_games.insert_one(dict(doc))
    return {k: doc[k] for k in FIELDS if k != "_id"}


@router.patch("/admin/live/games/{gid}")
async def toggle_game(gid: str, body: GamePatch, _: dict = Depends(require_admin)):
    r = await db.live_games.update_one({"id": gid, "deleted": {"$ne": True}}, {"$set": {"active": body.active}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Game not found")
    return {"ok": True}


@router.delete("/admin/live/games/{gid}")
async def delete_game(gid: str, _: dict = Depends(require_admin)):
    r = await db.live_games.update_one({"id": gid, "deleted": {"$ne": True}}, {"$set": {"deleted": True, "active": False}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Game not found")
    return {"ok": True}


# ---------- Launch ----------
class LaunchIn(BaseModel):
    game_id: str


async def _log_launch(user: dict, game: Optional[dict], status: str, reason: str = "", **extra) -> None:
    await db.live_sessions.insert_one({"id": new_id(), "user_id": user["id"], "user_email": user.get("email"),
                                       "player_id": user.get("bulk_player_id"), "game_id": (game or {}).get("id"),
                                       "game_uid": (game or {}).get("game_uid"), "game_name": (game or {}).get("name"),
                                       "provider": (game or {}).get("provider"), "status": status, "reason": reason,
                                       "created_at": now_iso(), **extra})


async def _fail(user: dict, game: Optional[dict], code: int, reason: str):
    await _log_launch(user, game, "failed", reason)
    raise HTTPException(status_code=code, detail=reason)


@router.post("/live/launch")
async def launch(body: LaunchIn, request: Request, user: dict = Depends(get_current_user)):
    if user["role"] != "user":
        raise HTTPException(status_code=403, detail="Only players can open live games")
    await _ensure()
    game = await db.live_games.find_one({"id": body.game_id, "active": True, "deleted": {"$ne": True}}, {"_id": 0})
    if not game:
        await _fail(user, None, 404, "Game not available")
    if game["provider"] not in await enabled_providers():
        await _fail(user, game, 403, "This provider is not available right now")
    if not _token() or not _secret():
        await _fail(user, game, 503, "Live casino is not set up yet. Please contact support.")
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "promo_balance": 1, "bulk_player_id": 1})
    balance = float(fresh.get("promo_balance", 0))
    if balance <= 0:
        await _fail(user, game, 400, "Your credit balance is empty. Make a deposit to play.")
    recent = (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat()
    if await db.live_sessions.find_one({"user_id": user["id"], "status": "launched", "created_at": {"$gt": recent}}, {"_id": 1}):
        raise HTTPException(status_code=429, detail="A game is already opening. Please wait a few seconds.")
    rate = await live_rate()
    pid = await player_id({**user, **fresh})
    wallet = round(balance * rate, 2)
    origin = request.headers.get("origin") or os.environ["FRONTEND_URL"]
    try:
        res = await infinity_launch(member_account(pid), wallet, game["game_uid"], origin.rstrip("/") + "/app/live-casino")
    except LaunchError as e:
        logger.warning(f"Launch failed for {user['id']} game={game['game_uid']}: {e.code}")
        await _fail({**user, "bulk_player_id": pid}, game, 502, "This game could not be opened right now. Please try again later.")
    await _log_launch({**user, "bulk_player_id": pid}, game, "launched", wallet_inr=wallet, wallet_usd=round(balance, 2), rate=rate,
                      request_id=res["request_id"])
    return {"url": res["game_url"], "wallet_inr": wallet}


# ---------- Callback ----------
def _f(form, key: str) -> float:
    try:
        v = float(form.get(key) or 0)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {key}")
    if not math.isfinite(v):
        raise HTTPException(status_code=400, detail=f"Invalid {key}")
    return round(v, 2)


async def _read_form(request: Request) -> dict:
    if "application/json" in request.headers.get("content-type", ""):
        return {k: str(v) for k, v in (await request.json()).items()}
    return {k: str(v) for k, v in (await request.form()).items()}


async def _log_cb(request: Request, form: dict, result: str, code: int) -> PlainTextResponse:
    await db.live_callbacks.insert_one({"id": new_id(), "ip": client_ip(request), "path": request.url.path,
                                        "game_round": form.get("game_round"), "mobile": form.get("mobile"),
                                        "fields": {k: v for k, v in form.items() if k != "token"}, "result": result,
                                        "http_status": code, "failed": code != 200, "created_at": now_iso()})
    return PlainTextResponse("ok" if code == 200 else result, status_code=code)


async def handle_callback(request: Request):
    form = {}
    try:
        form = await _read_form(request)
    except Exception:
        return await _log_cb(request, form, "unreadable body", 400)
    await _ensure()
    allowed = [ip.strip() for ip in os.environ.get("BULKAPI_CALLBACK_IPS", "").split(",") if ip.strip()]
    if allowed and client_ip(request) not in allowed:
        return await _log_cb(request, form, "ip not whitelisted", 403)
    if not _token() or not hmac.compare_digest(form.get("token", "").strip(), _token()):
        return await _log_cb(request, form, "invalid token", 403)
    rnd, mobile = form.get("game_round", "").strip(), form.get("mobile", "").strip()
    if not rnd or not mobile:
        return await _log_cb(request, form, "missing game_round or mobile", 400)
    try:
        bet, win = _f(form, "bet_amount"), _f(form, "win_amount")
    except HTTPException as e:
        return await _log_cb(request, form, e.detail, 400)
    if bet < 0 or win < 0:
        return await _log_cb(request, form, "negative amount", 400)
    user = await db.users.find_one({"bulk_player_id": mobile}, {"_id": 0, "id": 1, "email": 1})
    if not user:
        return await _log_cb(request, form, "unknown player", 404)
    game = await db.live_games.find_one({"game_uid": form.get("game_uid", "")}, {"_id": 0, "provider": 1, "name": 1})
    prev = await db.live_rounds.find_one({"game_round": rnd}, {"_id": 0})
    if prev and prev["user_id"] != user["id"]:
        return await _log_cb(request, form, "game_round belongs to another player", 409)
    rate = prev["rate"] if prev else await live_rate()
    change_usd = round((win - bet) / rate, 2)
    delta = round(change_usd - (prev["applied_usd"] if prev else 0), 2)
    raw = {k: v for k, v in form.items() if k != "token"}
    doc = {"game_round": rnd, "user_id": user["id"], "user_email": user.get("email"), "player_id": mobile,
           "game_uid": raw.get("game_uid"), "provider": (game or {}).get("provider", "Unknown"),
           "game_name": (game or {}).get("name"), "bet_inr": bet, "win_inr": win, "net_inr": round(win - bet, 2),
           "wallet_before": raw.get("wallet_before"), "wallet_after": raw.get("wallet_after"), "change": raw.get("change"),
           "currency": raw.get("currency_code") or "INR", "provider_ts": raw.get("timestamp"), "rate": rate,
           "applied_usd": change_usd, "settled": False, "raw": raw, "updated_at": now_iso(),
           "callbacks": (prev or {}).get("callbacks", 0) + 1}
    if prev:
        r = await db.live_rounds.update_one({"game_round": rnd, "applied_usd": prev["applied_usd"]}, {"$set": doc})
        if not r.modified_count:
            return await _log_cb(request, form, "duplicate (in progress)", 200)
    else:
        try:
            await db.live_rounds.insert_one({**doc, "created_at": now_iso()})
        except DuplicateKeyError:
            return await _log_cb(request, form, "duplicate (ignored)", 200)
    if not delta:
        await db.live_rounds.update_one({"game_round": rnd}, {"$set": {"settled": True}})
        return await _log_cb(request, form, "duplicate (no change)" if prev else "applied (zero change)", 200)
    u = await db.users.find_one_and_update({"id": user["id"]}, {"$inc": {"promo_balance": delta}},
                                           projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    await db.transactions.insert_one(make_tx(
        u, "live_round", "credit", delta,
        f"Live casino · {doc['game_name'] or doc['game_uid']} · bet ₹{bet:,.2f} win ₹{win:,.2f}",
        f"LIVE-{rnd[:20]}", u["promo_balance"]))
    await db.live_rounds.update_one({"game_round": rnd}, {"$set": {"settled": True, "balance_after_usd": u["promo_balance"]}})
    note = "updated" if prev else "applied"
    if u["promo_balance"] < 0:
        logger.error(f"Live round {rnd} left user {u['id']} negative: {u['promo_balance']}")
        note += " (balance negative)"
    return await _log_cb(request, form, f"{note} {delta:+.2f} USD", 200)


@router.post("/bulkapi/callback", response_class=PlainTextResponse)
async def callback(request: Request):
    return await handle_callback(request)


@router.post("/game_callback.php", response_class=PlainTextResponse)
async def callback_php(request: Request):
    return await handle_callback(request)


# ---------- Admin ----------
class RateIn(BaseModel):
    inr_rate: float = Field(gt=1, le=1000)


@router.put("/admin/live/rate")
async def set_rate(body: RateIn, admin: dict = Depends(require_admin)):
    await db.settings.update_one({"key": "live_casino"}, {"$set": {"inr_rate": body.inr_rate, "updated_by": admin["email"],
                                                                   "updated_at": now_iso()}}, upsert=True)
    return {"inr_rate": body.inr_rate}


async def _reachable() -> bool:
    try:
        async with httpx.AsyncClient(timeout=4, follow_redirects=False) as c:
            await c.get(INF_BASE + "/api/v1/providers")
        return True
    except httpx.HTTPError:
        return False


@router.get("/admin/live/status")
async def live_status(request: Request, _: dict = Depends(require_staff)):
    await _ensure()
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(":")[0]
    return {"callback_url": f"https://{host}/api/infinity/callback?token={_CACHE['cb_token']}",
            "source": _CACHE["source"], "token_is_url": _token().lower().startswith(("http://", "https://", "www.")),
            "token_mask": _mask(_token()), "secret_mask": _mask(_CACHE["secret"]),
            "reachable": await _reachable(), "failed_callbacks": await db.live_callbacks.count_documents({"failed": True}),
            "unsettled": await db.live_rounds.count_documents({"settled": False}),
            "token_set": bool(_token()), "secret_set": bool(_secret()), "secret_bytes": len(_secret()),
            "launch_url": LAUNCH_URL, "ip_whitelist": bool(os.environ.get("BULKAPI_CALLBACK_IPS")),
            "inr_rate": await live_rate(), "rounds": await db.live_rounds.count_documents({})}


@router.get("/admin/live/server-ip")
async def server_ip(request: Request, _: dict = Depends(require_staff)):
    domain = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(":")[0].removeprefix("www.")
    for url in ("https://api.ipify.org?format=json", "https://ifconfig.me/all.json"):
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(url)
            d = r.json()
            ip = d.get("ip") or d.get("ip_addr")
            if ip:
                return {"ip": ip, "domain": domain, "checked_at": now_iso()}
        except (httpx.HTTPError, ValueError):
            continue
    raise HTTPException(status_code=502, detail="Could not detect the server IP right now. Try again.")


class TestIn(BaseModel):
    game_uid: str = Field(min_length=1, max_length=80)


ERROR_WORDS = ("not found", "missing", "invalid", "error", "expired", "denied", "disabled", "failed")


async def probe(game_uid: str) -> dict:
    try:
        res = await infinity_launch("scm_test_9000000000", 100.0, game_uid.strip(), os.environ["FRONTEND_URL"].rstrip("/") + "/app/live-casino")
    except LaunchError as e:
        logger.info(f"Infinity probe game_uid={game_uid} failed {e.code}")
        return {"ok": False, "status": e.status, "redirect": "", "detail": f"{e.code} {e.detail}".strip()[:400]}
    return {"ok": True, "status": 200, "redirect": res["game_url"][:300], "detail": f"request_id {res['request_id']}"}


@router.post("/admin/live/test")
async def test_launch(body: TestIn, _: dict = Depends(require_admin)):
    return await probe(body.game_uid)


@router.get("/admin/live/ggr")
async def live_ggr(_: dict = Depends(require_staff)):
    rows = await db.live_rounds.aggregate([
        {"$group": {"_id": "$provider", "rounds": {"$sum": 1}, "bets": {"$sum": "$bet_inr"}, "wins": {"$sum": "$win_inr"},
                    "players": {"$addToSet": "$user_id"}}},
        {"$sort": {"bets": -1}}]).to_list(100)
    out = [{"provider": r["_id"], "rounds": r["rounds"], "players": len(r["players"]), "bets_inr": round(r["bets"], 2),
            "wins_inr": round(r["wins"], 2), "ggr_inr": round(r["bets"] - r["wins"], 2)} for r in rows]
    recent = await db.live_rounds.find({}, {"_id": 0, "raw": 0}).sort("updated_at", -1).to_list(50)
    return {"providers": out, "recent": recent}


def _q(user: Optional[str]) -> dict:
    return {"user_email": {"$regex": f"^{re.escape(user.strip())}", "$options": "i"}} if user and user.strip() else {}


@router.get("/admin/live/sessions")
async def live_sessions(user: Optional[str] = None, status: Optional[str] = None, _: dict = Depends(require_staff)):
    q = {**_q(user), **({"status": status} if status in ("launched", "failed") else {})}
    return await db.live_sessions.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.get("/admin/live/rounds")
async def live_rounds(user: Optional[str] = None, result: Optional[str] = None, _: dict = Depends(require_staff)):
    q = _q(user)
    if result == "win":
        q["net_inr"] = {"$gt": 0}
    elif result == "loss":
        q["net_inr"] = {"$lt": 0}
    return await db.live_rounds.find(q, {"_id": 0, "raw": 0}).sort("updated_at", -1).to_list(200)


@router.get("/admin/live/players")
async def live_players(_: dict = Depends(require_staff)):
    rows = await db.live_rounds.aggregate([
        {"$group": {"_id": "$user_id", "email": {"$first": "$user_email"}, "player_id": {"$first": "$player_id"},
                    "rounds": {"$sum": 1}, "bets": {"$sum": "$bet_inr"}, "wins": {"$sum": "$win_inr"},
                    "net_usd": {"$sum": "$applied_usd"}, "last": {"$max": "$updated_at"}}},
        {"$sort": {"bets": -1}}, {"$limit": 200}]).to_list(200)
    return [{"user_id": r["_id"], "email": r["email"], "player_id": r["player_id"], "rounds": r["rounds"],
             "bets_inr": round(r["bets"], 2), "wins_inr": round(r["wins"], 2), "ggr_inr": round(r["bets"] - r["wins"], 2),
             "net_usd": round(r["net_usd"], 2), "last": r["last"]} for r in rows]


@router.get("/admin/live/callbacks")
async def live_callbacks(failed: bool = False, _: dict = Depends(require_staff)):
    return await db.live_callbacks.find({"failed": True} if failed else {}, {"_id": 0}).sort("created_at", -1).to_list(200)


class CredsIn(BaseModel):
    api_token: Optional[str] = Field(default=None, max_length=300)
    secret_key: Optional[str] = Field(default=None, max_length=300)


@router.put("/admin/live/credentials")
async def save_credentials(body: CredsIn, admin: dict = Depends(require_admin)):
    token, secret = (body.api_token or "").strip(), (body.secret_key or "").strip()
    if not token and not secret:
        raise HTTPException(status_code=400, detail="Enter the API Token, the Secret Key or both")
    if token.lower().startswith(("http://", "https://", "www.")):
        raise HTTPException(status_code=400, detail="This looks like a website link, not the API Token. Copy the API Token field from the BULKAPI portal.")
    upd = {"updated_by": admin["email"], "updated_at": now_iso()}
    if token:
        upd["token_enc"] = _FERNET.encrypt(token.encode()).decode()
    if secret:
        upd["secret_enc"] = _FERNET.encrypt(secret.encode()).decode()
    await db.settings.update_one({"key": "infinity_creds"}, {"$set": upd}, upsert=True)
    await db.audit_logs.insert_one({"id": new_id(), "action": "bulkapi_credentials_updated", "by": admin["email"],
                                    "fields": [k for k, v in (("token", token), ("secret", secret)) if v], "created_at": now_iso()})
    _CACHE["at"] = 0.0
    await _ensure()
    return {"ok": True, "token_mask": _mask(_token()), "secret_mask": _mask(_CACHE["secret"]), "warning": ""}


@router.delete("/admin/live/credentials")
async def clear_credentials(admin: dict = Depends(require_admin)):
    await db.settings.update_one({"key": "infinity_creds"}, {"$unset": {"token_enc": "", "secret_enc": ""}})
    await db.audit_logs.insert_one({"id": new_id(), "action": "bulkapi_credentials_cleared", "by": admin["email"], "created_at": now_iso()})
    _CACHE["at"] = 0.0
    await _ensure()
    return {"ok": True, "source": _CACHE["source"]}


HEADERS = {"name": ("name", "game", "game name", "game_name", "title"), "provider": ("provider", "vendor", "brand"),
           "game_uid": ("game_uid", "uid", "game uid", "game id", "game_id", "gameuid", "code", "game code")}


def _rows(filename: str, data: bytes) -> list:
    if filename.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
        return [["" if c is None else str(c).strip() for c in r] for r in ws.iter_rows(values_only=True)]
    text = data.decode("utf-8-sig", errors="replace")
    return [[c.strip() for c in r] for r in csv.reader(io.StringIO(text))]


@router.post("/admin/live/games/import")
async def import_games(file: UploadFile = File(...), admin: dict = Depends(require_admin)):
    name = file.filename or ""
    if not name.lower().endswith((".csv", ".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Upload a .csv or .xlsx file")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File is larger than 5 MB")
    try:
        rows = [r for r in _rows(name, data) if any(r)]
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this file")
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="The file has no game rows")
    head = [h.lower().strip() for h in rows[0]]
    col = {k: next((i for i, h in enumerate(head) if h in alts), None) for k, alts in HEADERS.items()}
    if col["name"] is None or col["game_uid"] is None:
        raise HTTPException(status_code=400, detail="First row must have column names: name, provider, game_uid")
    existing = {g["game_uid"] for g in await db.live_games.find({"deleted": {"$ne": True}}, {"_id": 0, "game_uid": 1}).to_list(20000)}
    added, skipped, errors, docs = 0, 0, [], []
    for n, r in enumerate(rows[1:], start=2):
        get = lambda k: (r[col[k]] if col[k] is not None and col[k] < len(r) else "").strip()
        gname, uid, prov = get("name"), get("game_uid"), get("provider")
        prov = prov if len(prov) >= 2 else "Other"
        if len(gname) < 2 or not uid or len(uid) > 80 or len(gname) > 80:
            errors.append(f"Row {n}: missing or too long name / game_uid")
            continue
        if uid in existing:
            skipped += 1
            continue
        existing.add(uid)
        docs.append({"id": new_id(), "name": gname, "provider": prov[:40], "game_uid": uid, "image_id": None, "active": True,
                     "created_by": admin["email"], "created_at": now_iso(), "deleted": False})
        added += 1
    if docs:
        await db.live_games.insert_many(docs)
        from live_providers import ensure_providers
        await ensure_providers({d["provider"] for d in docs}, admin["email"])
    return {"added": added, "skipped": skipped, "errors": errors[:50], "error_count": len(errors)}
