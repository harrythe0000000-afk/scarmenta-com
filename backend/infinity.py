import hashlib
import hmac
import json
import logging
import math
import os
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

import bulkapi
from bulkapi import INF_BASE, _ensure, _token, live_rate
from core import now, client_ip, db, get_current_user, make_tx, new_id, now_iso, require_admin, require_staff
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


async def sync_provider(brand_id: str, name: str, by: str) -> dict:
    j = await _catalog("/api/v1/games", provider=brand_id)
    games = [g for g in j.get("games") or [] if isinstance(g, dict) and str(g.get("game_uid", "")).strip()]
    await ensure_providers({name}, by)
    await db.live_providers.update_one({"name": name}, {"$set": {"brand_id": brand_id}})
    added = updated = 0
    seen = set()
    for g in games:
        uid = str(g["game_uid"]).strip()[:80]
        seen.add(uid)
        doc = {"name": str(g.get("name") or uid)[:80], "provider": name, "category": g.get("category"),
               "image_url": g.get("img") if str(g.get("img", "")).startswith("https://") else None, "catalog_missing": False}
        live = str(g.get("status", "Active")).lower() == "active"
        r = await db.live_games.update_one({"game_uid": uid, "deleted": {"$ne": True}}, {"$set": doc})
        if r.matched_count:
            await db.live_games.update_one({"game_uid": uid, "deleted": {"$ne": True}, "broken": {"$ne": True},
                                            "admin_off": {"$ne": True}}, {"$set": {"active": live}})
            updated += 1
            continue
        await db.live_games.insert_one({"id": new_id(), "game_uid": uid, "image_id": None, "deleted": False, "active": live,
                                        "created_by": by, "created_at": now_iso(), **doc})
        added += 1
    gone = 0
    if games:
        r = await db.live_games.update_many({"provider": name, "deleted": {"$ne": True}, "game_uid": {"$nin": list(seen)}},
                                            {"$set": {"active": False, "catalog_missing": True}})
        gone = r.modified_count
    logger.info(f"Catalog sync {name}: {added} added, {updated} updated, {gone} removed")
    return {"added": added, "updated": updated, "removed": gone, "total": len(games)}


@router.post("/admin/live/catalog/import")
async def catalog_import(body: ImportIn, admin: dict = Depends(require_admin)):
    return await sync_provider(body.brand_id, body.name, admin["email"])


AUTO_PROVIDERS = [("59", "Evolution Live (Asia)"), ("78", "Ezugi"), ("55", "PragmaticPlayLive-EU"), ("57", "Spribe"), ("49", "JILI")]


async def _auto_one(brand: str, name: str) -> bool:
    await sync_provider(brand, name, "auto import")
    games = await db.live_games.find({"provider": name, "deleted": {"$ne": True}, "active": True}, {"_id": 0, "game_uid": 1}).to_list(3)
    res = None
    for g in games:
        res = await bulkapi.probe(g["game_uid"])
        if res["ok"] or not res.get("game_missing"):
            break
    if not res:
        return False
    upd = {"last_test": {"ok": res["ok"], "status": res["status"], "game_uid": g["game_uid"], "detail": res["detail"][:300],
                         "by": "auto import", "at": now_iso()}}
    if res["ok"]:
        upd["enabled"] = True
    await db.live_providers.update_one({"name": name}, {"$set": upd})
    logger.info(f"Auto import {name}: ok={res['ok']} {res['detail'][:120]}")
    return res["ok"]


async def auto_import() -> None:
    try:
        await _ensure()
        if not _token():
            return
        st = await db.settings.find_one({"key": "auto_import_v1"}, {"_id": 0, "done": 1}) or {}
        ready = await db.live_providers.distinct("brand_id", {"enabled": True})
        todo = [p for p in AUTO_PROVIDERS if p[0] not in st.get("done", []) and p[0] not in ready]
        if not todo:
            return
        await db.locks.delete_one({"_id": "auto_import", "at": {"$lt": (now() - timedelta(minutes=15)).isoformat()}})
        try:
            await db.locks.insert_one({"_id": "auto_import", "at": now_iso()})
        except DuplicateKeyError:
            return
        try:
            for brand, name in todo:
                try:
                    if await _auto_one(brand, name):
                        await db.settings.update_one({"key": "auto_import_v1"}, {"$addToSet": {"done": brand}}, upsert=True)
                except HTTPException as e:
                    logger.warning(f"Auto import {name} failed: {e.detail}")
        finally:
            await db.locks.delete_one({"_id": "auto_import"})
    except Exception:
        logger.exception("Auto import failed")


async def _run_sync(run_id: str) -> None:
    await auto_import()
    results = {}
    for p in await db.live_providers.find({"brand_id": {"$exists": True, "$ne": None}}, {"_id": 0, "name": 1, "brand_id": 1}).to_list(200):
        try:
            results[p["name"]] = await sync_provider(p["brand_id"], p["name"], "daily sync")
        except HTTPException as e:
            results[p["name"]] = {"error": e.detail}
        except Exception as e:
            logger.exception(f"Catalog sync failed for {p['name']}")
            results[p["name"]] = {"error": e.__class__.__name__}
    await db.cron_runs.update_one({"run_id": run_id}, {"$set": {"status": "done", "results": results, "finished_at": now_iso()}})


@router.post("/cron/catalog-sync")
async def cron_catalog_sync(request: Request, tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("authorization", "")
    secret = os.environ["WEBHOOK_CRON_SECRET"]
    if not auth.startswith("Bearer ") or not hmac.compare_digest(auth[7:], secret):
        return JSONResponse({"ok": False}, status_code=401)
    try:
        env = json.loads(await request.body() or b"{}")
    except ValueError:
        return JSONResponse({"ok": False}, status_code=400)
    run_id = request.headers.get("x-webhook-id") or (env.get("run_id") if isinstance(env, dict) else None) or new_id()
    try:
        await db.cron_runs.insert_one({"run_id": str(run_id)[:100], "job": "catalog-sync", "status": "queued", "created_at": now_iso()})
    except DuplicateKeyError:
        return JSONResponse({"ok": True, "duplicate": True})
    tasks.add_task(_run_sync, str(run_id)[:100])
    return JSONResponse({"ok": True})


@router.get("/admin/live/sync-runs")
async def sync_runs(_: dict = Depends(require_admin)):
    return await db.cron_runs.find({"job": "catalog-sync"}, {"_id": 0}).sort("created_at", -1).to_list(10)


@router.get("/live/my-rounds")
async def my_rounds(user: dict = Depends(get_current_user)):
    return await db.live_rounds.find({"user_id": user["id"]}, {"_id": 0, "game_round": 1, "game_name": 1, "game_uid": 1, "provider": 1,
                                                               "bet_inr": 1, "win_inr": 1, "net_inr": 1, "applied_usd": 1,
                                                               "updated_at": 1}).sort("updated_at", -1).to_list(200)


@router.get("/live/session-result")
async def session_result(since: str, user: dict = Depends(get_current_user)):
    try:
        datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time")
    rows = await db.live_events.aggregate([
        {"$match": {"user_id": user["id"], "created_at": {"$gte": since}}},
        {"$group": {"_id": None, "bet": {"$sum": "$bet_inr"}, "win": {"$sum": "$win_inr"}, "usd": {"$sum": "$delta_usd"}, "n": {"$sum": 1}}}]).to_list(1)
    r = rows[0] if rows else {"bet": 0, "win": 0, "usd": 0, "n": 0}
    top = await db.live_events.aggregate([
        {"$match": {"user_id": user["id"], "created_at": {"$gte": since}}},
        {"$group": {"_id": {"g": "$game_uid", "r": "$game_round"}, "net": {"$sum": {"$subtract": ["$win_inr", "$bet_inr"]}}}},
        {"$sort": {"net": -1}}, {"$limit": 1}]).to_list(1)
    return {"top_round_inr": round(top[0]["net"], 2) if top else 0, "events": r["n"], "bet_inr": round(r["bet"], 2), "win_inr": round(r["win"], 2), "net_inr": round(r["win"] - r["bet"], 2),
            "net_usd": round(r["usd"], 2)}


@router.get("/admin/live/ggr-alert")
async def ggr_alert(_: dict = Depends(require_staff)):
    return await db.settings.find_one({"key": "infinity_ggr_alert"}, {"_id": 0, "message": 1, "at": 1, "kind": 1, "ip": 1}) or {}


def _mask(name: str) -> str:
    name = (name or "Player").strip() or "Player"
    return f"{name[:2]}***"


@router.get("/live/big-wins")
async def big_wins(_: dict = Depends(get_current_user)):
    rows = await db.live_rounds.find({"net_inr": {"$gte": 100}}, {"_id": 0, "user_id": 1, "game_name": 1, "provider": 1, "net_inr": 1,
                                                                 "updated_at": 1}).sort("updated_at", -1).to_list(15)
    names = {u["id"]: u.get("name") for u in await db.users.find({"id": {"$in": list({r["user_id"] for r in rows})}},
                                                                   {"_id": 0, "id": 1, "name": 1}).to_list(15)}
    return [{"player": _mask(names.get(r["user_id"])), "game": r.get("game_name") or r.get("provider"), "net_inr": r["net_inr"],
             "at": r.get("updated_at")} for r in rows]
