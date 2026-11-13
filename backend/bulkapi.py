import base64
import hmac
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
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core import client_ip, db, get_current_user, make_tx, new_id, now_iso, require_admin, require_staff

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
LAUNCH_URL = os.environ["BULKAPI_BASE_URL"].rstrip("/") + "/launch_game"
DEFAULT_RATE = 95.0


def _token() -> str:
    return os.environ.get("BULKAPI_API_TOKEN", "").strip()


def _secret() -> bytes:
    return os.environ.get("BULKAPI_SECRET_KEY", "").strip().encode()


def encrypt_payload(data: dict) -> str:
    # PHP openssl AES-256-ECB: key null-padded/truncated to 32 bytes, PKCS7 padding, base64 output
    key = _secret()[:32].ljust(32, b"\0")
    padder = padding.PKCS7(128).padder()
    raw = padder.update(json.dumps(data, separators=(",", ":")).encode()) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return base64.b64encode(enc.update(raw) + enc.finalize()).decode()


def build_launch_url(player: str, wallet: float, game_uid: str) -> str:
    token, ts = _token(), int(time.time() * 1000)
    payload = encrypt_payload({"user_id": player, "wallet_amount": wallet, "game_uid": game_uid, "token": token, "timestamp": ts})
    return LAUNCH_URL + "?" + urlencode({"user_id": player, "wallet_amount": wallet, "game_uid": game_uid,
                                        "token": token, "timestamp": ts, "payload": payload})


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


FIELDS = {"_id": 0, "id": 1, "name": 1, "provider": 1, "game_uid": 1, "image_id": 1, "active": 1, "created_at": 1}


@router.get("/live/games")
async def player_games(_: dict = Depends(get_current_user)):
    rows = await db.live_games.find({"active": True, "deleted": {"$ne": True}}, FIELDS).sort("provider", 1).to_list(500)
    return [{k: v for k, v in g.items() if k not in ("_id", "game_uid")} for g in rows]


@router.get("/admin/live/games")
async def admin_games(_: dict = Depends(require_staff)):
    rows = await db.live_games.find({"deleted": {"$ne": True}}, FIELDS).sort("created_at", -1).to_list(500)
    return [{k: v for k, v in g.items() if k != "_id"} for g in rows]


@router.post("/admin/live/games")
async def add_game(body: GameIn, admin: dict = Depends(require_admin)):
    if await db.live_games.find_one({"game_uid": body.game_uid.strip(), "deleted": {"$ne": True}}):
        raise HTTPException(status_code=400, detail="A game with this game_uid already exists")
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
async def launch(body: LaunchIn, user: dict = Depends(get_current_user)):
    if user["role"] != "user":
        raise HTTPException(status_code=403, detail="Only players can open live games")
    game = await db.live_games.find_one({"id": body.game_id, "active": True, "deleted": {"$ne": True}}, {"_id": 0})
    if not game:
        await _fail(user, None, 404, "Game not available")
    if not _token() or not _secret():
        await _fail(user, game, 503, "Live casino is not set up yet. Please contact support.")
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "promo_balance": 1, "bulk_player_id": 1})
    balance = float(fresh.get("promo_balance", 0))
    if balance <= 0:
        await _fail(user, game, 400, "Your credit balance is empty. Make a deposit to play.")
    rate = await live_rate()
    pid = await player_id({**user, **fresh})
    wallet = round(balance * rate, 2)
    url = build_launch_url(pid, wallet, game["game_uid"])
    await _log_launch({**user, "bulk_player_id": pid}, game, "launched", wallet_inr=wallet, wallet_usd=round(balance, 2), rate=rate)
    return {"url": url, "wallet_inr": wallet}


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
            await c.head(LAUNCH_URL)
        return True
    except httpx.HTTPError:
        return False


@router.get("/admin/live/status")
async def live_status(_: dict = Depends(require_staff)):
    return {"reachable": await _reachable(), "failed_callbacks": await db.live_callbacks.count_documents({"failed": True}),
            "unsettled": await db.live_rounds.count_documents({"settled": False}),
            "token_set": bool(_token()), "secret_set": bool(_secret()), "secret_bytes": len(_secret()),
            "launch_url": LAUNCH_URL, "ip_whitelist": bool(os.environ.get("BULKAPI_CALLBACK_IPS")),
            "inr_rate": await live_rate(), "rounds": await db.live_rounds.count_documents({})}


class TestIn(BaseModel):
    game_uid: str = Field(min_length=1, max_length=80)


@router.post("/admin/live/test")
async def test_launch(body: TestIn, _: dict = Depends(require_admin)):
    if not _token() or not _secret():
        raise HTTPException(status_code=400, detail="API token or secret key is missing")
    url = build_launch_url("9000000000", 100.0, body.game_uid.strip())
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as c:
            r = await c.get(url)
    except httpx.HTTPError as e:
        return {"ok": False, "status": 0, "detail": f"Could not reach BULKAPI: {e.__class__.__name__}"}
    location = r.headers.get("location", "")
    text = r.text[:400]
    ok = (r.is_redirect and bool(location)) or (r.status_code == 200 and "not found" not in text.lower()
                                                 and "missing" not in text.lower() and "invalid" not in text.lower())
    return {"ok": ok, "status": r.status_code, "redirect": location[:300], "detail": text}


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
