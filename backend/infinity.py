import hashlib
import hmac
import json
import logging
import math

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

import bulkapi
from bulkapi import INF_BASE, _ensure, _token, live_rate
from core import client_ip, db, make_tx, new_id, now_iso, require_admin
from live_providers import ensure_providers

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
MAX_AMOUNT = 1_000_000_000


def _resp(ok: bool, code: int = 200) -> JSONResponse:
    return JSONResponse({"ok": ok}, status_code=code)


async def _log(request: Request, data: dict, result: str, code: int) -> JSONResponse:
    await db.live_callbacks.insert_one({"id": new_id(), "ip": client_ip(request), "path": request.url.path,
                                        "game_round": str(data.get("game_round", ""))[:80] if isinstance(data, dict) else None,
                                        "mobile": str(data.get("member_account", ""))[:80] if isinstance(data, dict) else None,
                                        "fields": data if isinstance(data, dict) else {}, "result": result,
                                        "http_status": code, "failed": code != 200, "created_at": now_iso()})
    return _resp(code == 200, code)


def _amount(v) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise ValueError
    f = float(v)
    if not math.isfinite(f) or f < 0 or f > MAX_AMOUNT or abs(f - round(f, 2)) > 1e-6:
        raise ValueError
    return round(f, 2)


@router.post("/infinity/callback")
async def infinity_callback(request: Request, token: str = ""):
    await _ensure()
    data = {}
    if not bulkapi._CACHE["cb_token"] or not hmac.compare_digest(token, bulkapi._CACHE["cb_token"]):
        return await _log(request, data, "invalid callback token", 403)
    try:
        data = json.loads(await request.body())
    except ValueError:
        return await _log(request, {}, "body is not JSON", 400)
    if not isinstance(data, dict):
        return await _log(request, {}, "body is not a JSON object", 400)
    for f in ("member_account", "game_uid", "game_round"):
        if not isinstance(data.get(f), (str, int)) or str(data.get(f)) == "":
            return await _log(request, data, f"missing {f}", 400)
    try:
        bet, win = _amount(data.get("bet_amount")), _amount(data.get("win_amount"))
    except (ValueError, TypeError):
        return await _log(request, data, "invalid bet_amount or win_amount", 400)
    member, uid, rnd = str(data["member_account"]), str(data["game_uid"]), str(data["game_round"])
    serial, ts = str(data.get("serial_number") or ""), str(data.get("timestamp") or "")
    if not serial and not ts:
        return await _log(request, data, "missing serial_number and timestamp", 400)
    identity = ["serial", serial] if serial else ["timestamp_amounts", ts, f"{bet:.2f}", f"{win:.2f}"]
    key = hashlib.sha256(json.dumps([member, uid, rnd, identity]).encode()).hexdigest()
    fp = hashlib.sha256(f"{bet:.2f}|{win:.2f}".encode()).hexdigest()
    pid = member.removeprefix("scm_")
    user = await db.users.find_one({"bulk_player_id": pid}, {"_id": 0, "id": 1, "email": 1})
    if not user:
        return await _log(request, data, "unknown player", 404)
    rate = await live_rate()
    delta = round((win - bet) / rate, 2)
    try:
        await db.live_events.insert_one({"event_key": key, "fingerprint": fp, "user_id": user["id"], "member": member,
                                         "game_uid": uid, "game_round": rnd, "serial": serial, "provider_ts": ts,
                                         "bet_inr": bet, "win_inr": win, "rate": rate, "delta_usd": delta,
                                         "inf_balance": data.get("inf_balance"), "request_id": data.get("inf_request_id"),
                                         "applied": False, "created_at": now_iso()})
    except DuplicateKeyError:
        prev = await db.live_events.find_one({"event_key": key}, {"_id": 0, "fingerprint": 1})
        if prev and hmac.compare_digest(prev["fingerprint"], fp):
            return await _log(request, data, "duplicate (ignored)", 200)
        return await _log(request, data, "event conflict: same event, different amounts", 409)
    game = await db.live_games.find_one({"game_uid": uid}, {"_id": 0, "provider": 1, "name": 1}) or {}
    rid = f"{uid}:{rnd}:{pid}"
    await db.live_rounds.update_one({"game_round": rid}, {
        "$inc": {"bet_inr": bet, "win_inr": win, "net_inr": round(win - bet, 2), "applied_usd": delta, "callbacks": 1},
        "$set": {"user_id": user["id"], "user_email": user.get("email"), "player_id": member, "game_uid": uid,
                 "provider": game.get("provider", "Unknown"), "game_name": game.get("name"), "rate": rate, "currency": "INR",
                 "wallet_after": data.get("inf_balance"), "settled": True, "updated_at": now_iso()},
        "$setOnInsert": {"created_at": now_iso()}}, upsert=True)
    if delta:
        u = await db.users.find_one_and_update({"id": user["id"]}, {"$inc": {"promo_balance": delta}},
                                               projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
        await db.transactions.insert_one(make_tx(
            u, "live_round", "credit", delta,
            f"Live casino · {game.get('name') or uid} · bet ₹{bet:,.2f} win ₹{win:,.2f}", f"LIVE-{key[:16]}", u["promo_balance"]))
        if u["promo_balance"] < 0:
            logger.error(f"Infinity event {key} left user {u['id']} negative: {u['promo_balance']}")
    await db.live_events.update_one({"event_key": key}, {"$set": {"applied": True}})
    return await _log(request, data, f"applied {delta:+.2f} USD", 200)


async def _catalog(path: str, **params) -> dict:
    await _ensure()
    if not _token():
        raise HTTPException(status_code=400, detail="Save the InfinityAPI API Key first")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5)) as c:
            r = await c.get(INF_BASE + path, params={"api_key": _token(), **params})
        j = r.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="InfinityAPI did not answer in time")
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=424, detail="InfinityAPI returned an unreadable answer")
    if not isinstance(j, dict) or j.get("ok") is not True:
        err = (j or {}).get("error") or (j or {}).get("message") if isinstance(j, dict) else None
        raise HTTPException(status_code=424, detail=f"InfinityAPI: {err or 'request rejected'} (HTTP {r.status_code})")
    return j


@router.get("/admin/live/catalog/providers")
async def catalog_providers(_: dict = Depends(require_admin)):
    j = await _catalog("/api/v1/providers")
    return [{"brand_id": str(p.get("brand_id", "")), "name": str(p.get("name", ""))[:40], "logo": p.get("logo"),
             "games_count": p.get("games_count"), "status": p.get("status")} for p in j.get("providers") or [] if isinstance(p, dict)]


class ImportIn(BaseModel):
    brand_id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=40)


@router.post("/admin/live/catalog/import")
async def catalog_import(body: ImportIn, admin: dict = Depends(require_admin)):
    j = await _catalog("/api/v1/games", provider=body.brand_id)
    games = [g for g in j.get("games") or [] if isinstance(g, dict) and str(g.get("game_uid", "")).strip()]
    await ensure_providers({body.name}, admin["email"])
    await db.live_providers.update_one({"name": body.name}, {"$set": {"brand_id": body.brand_id}})
    added = updated = 0
    for g in games:
        uid = str(g["game_uid"]).strip()[:80]
        doc = {"name": str(g.get("name") or uid)[:80], "provider": body.name, "image_url": g.get("img") if str(g.get("img", "")).startswith("https://") else None,
               "category": g.get("category"), "active": str(g.get("status", "Active")).lower() == "active"}
        r = await db.live_games.update_one({"game_uid": uid, "deleted": {"$ne": True}}, {"$set": doc})
        if r.matched_count:
            updated += 1
            continue
        await db.live_games.insert_one({"id": new_id(), "game_uid": uid, "image_id": None, "deleted": False,
                                        "created_by": admin["email"], "created_at": now_iso(), **doc})
        added += 1
    logger.info(f"Catalog import {body.name}: {added} added, {updated} updated")
    return {"added": added, "updated": updated, "total": len(games)}
