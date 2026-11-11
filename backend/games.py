import hashlib
import hmac
import secrets
from datetime import timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core import db, get_current_user, make_tx, new_id, now, now_iso, require_admin

router = APIRouter(prefix="/api")


class ProviderIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    code: str = Field(pattern=r"^[a-z0-9_-]{2,30}$")
    launch_url: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = Field(default=None, max_length=300)
    status: Literal["active", "inactive"] = "inactive"


class LaunchIn(BaseModel):
    provider_id: str
    game_code: Optional[str] = Field(default=None, max_length=60)


class SessionIn(BaseModel):
    session_token: str


class BetIn(SessionIn):
    transaction_id: str = Field(min_length=1, max_length=100)
    round_id: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    game_code: Optional[str] = Field(default=None, max_length=60)


class WinIn(BetIn):
    amount: float = Field(ge=0)


class RollbackIn(SessionIn):
    transaction_id: str = Field(min_length=1, max_length=100)
    ref_transaction_id: str = Field(min_length=1, max_length=100)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _public(p: dict) -> dict:
    p.pop("_id", None)
    p.pop("api_key_hash", None)
    return p


def _validate_url(url: Optional[str]) -> Optional[str]:
    if url and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Launch URL must start with https://")
    return url or None


# ---------- Admin: provider management ----------
@router.get("/admin/providers")
async def list_providers(_: dict = Depends(require_admin)):
    return await db.providers.find({}, {"_id": 0, "api_key_hash": 0}).sort("created_at", -1).to_list(200)


@router.post("/admin/providers")
async def create_provider(body: ProviderIn, _: dict = Depends(require_admin)):
    if await db.providers.find_one({"code": body.code}):
        raise HTTPException(status_code=400, detail="Provider code already exists")
    key = "pk_" + secrets.token_urlsafe(32)
    p = {"id": new_id(), **body.model_dump(), "launch_url": _validate_url(body.launch_url),
         "api_key_hash": _hash(key), "api_key_last4": key[-4:], "created_at": now_iso()}
    await db.providers.insert_one(p)
    return {**_public(p), "api_key": key}


@router.put("/admin/providers/{pid}")
async def update_provider(pid: str, body: ProviderIn, _: dict = Depends(require_admin)):
    if await db.providers.find_one({"code": body.code, "id": {"$ne": pid}}):
        raise HTTPException(status_code=400, detail="Provider code already exists")
    data = {**body.model_dump(), "launch_url": _validate_url(body.launch_url), "updated_at": now_iso()}
    p = await db.providers.find_one_and_update({"id": pid}, {"$set": data}, projection={"_id": 0, "api_key_hash": 0},
                                               return_document=ReturnDocument.AFTER)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    return p


@router.post("/admin/providers/{pid}/rotate-key")
async def rotate_key(pid: str, _: dict = Depends(require_admin)):
    key = "pk_" + secrets.token_urlsafe(32)
    p = await db.providers.find_one_and_update({"id": pid}, {"$set": {"api_key_hash": _hash(key), "api_key_last4": key[-4:]}},
                                               projection={"_id": 0, "api_key_hash": 0}, return_document=ReturnDocument.AFTER)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {**p, "api_key": key}


@router.get("/admin/game-transactions")
async def admin_game_txs(provider_id: Optional[str] = None, type: Optional[str] = None, q: Optional[str] = None,
                         _: dict = Depends(require_admin)):
    query: dict = {}
    if provider_id:
        query["provider_id"] = provider_id
    if type:
        query["type"] = type
    if q:
        import re
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"user_email": rx}, {"round_id": rx}, {"external_tx_id": rx}]
    return await db.game_transactions.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)


@router.get("/admin/game-stats")
async def admin_game_stats(_: dict = Depends(require_admin)):
    rows = await db.game_transactions.aggregate([
        {"$match": {"status": "ok"}},
        {"$group": {"_id": {"p": "$provider_id", "t": "$type"}, "sum": {"$sum": "$amount"}, "n": {"$sum": 1}}}]).to_list(1000)
    providers = {p["id"]: p["name"] for p in await db.providers.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(200)}
    out: dict = {}
    for r in rows:
        pid = r["_id"]["p"]
        o = out.setdefault(pid, {"provider_id": pid, "provider_name": providers.get(pid, "—"), "bets": 0, "wins": 0,
                                 "rollbacks": 0, "bet_count": 0})
        if r["_id"]["t"] == "bet":
            o["bets"] += r["sum"]
            o["bet_count"] += r["n"]
        elif r["_id"]["t"] == "win":
            o["wins"] += r["sum"]
        elif r["_id"]["t"] == "rollback":
            o["rollbacks"] += r["sum"]
    items = list(out.values())
    for o in items:
        o["ggr"] = round(o["bets"] - o["rollbacks"] - o["wins"], 2)
    totals = {k: round(sum(o[k] for o in items), 2) for k in ("bets", "wins", "rollbacks", "ggr")}
    return {"providers": items, "totals": totals,
            "active_sessions": await db.game_sessions.count_documents({"expires_at": {"$gt": now()}})}


# ---------- Player: games lobby ----------
@router.get("/games/providers")
async def player_providers(_: dict = Depends(get_current_user)):
    rows = await db.providers.find({"status": "active"}, {"_id": 0, "id": 1, "name": 1, "code": 1, "description": 1,
                                                         "launch_url": 1}).sort("name", 1).to_list(200)
    return [{**{k: v for k, v in r.items() if k != "launch_url"}, "connected": bool(r.get("launch_url"))} for r in rows]


@router.post("/games/launch")
async def launch(body: LaunchIn, user: dict = Depends(get_current_user)):
    if user.get("role") != "user":
        raise HTTPException(status_code=403, detail="Only player accounts can play")
    p = await db.providers.find_one({"id": body.provider_id, "status": "active"}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Provider not available")
    token = secrets.token_urlsafe(32)
    await db.game_sessions.insert_one({"token": token, "user_id": user["id"], "provider_id": p["id"],
                                       "game_code": body.game_code, "created_at": now_iso(),
                                       "expires_at": now() + timedelta(hours=4)})
    url = None
    if p.get("launch_url"):
        sep = "&" if "?" in p["launch_url"] else "?"
        url = f"{p['launch_url']}{sep}token={token}&currency=USD&lang=en" + (f"&game={body.game_code}" if body.game_code else "")
    return {"session_token": token, "launch_url": url, "provider": p["name"]}


@router.get("/games/history")
async def player_history(user: dict = Depends(get_current_user)):
    return await db.game_transactions.find({"user_id": user["id"], "status": "ok"}, {"_id": 0}).sort("created_at", -1).to_list(500)


# ---------- Provider seamless-wallet API ----------
async def get_provider(request: Request) -> dict:
    key = request.headers.get("X-Provider-Key", "")
    if not key:
        raise HTTPException(status_code=401, detail="Missing X-Provider-Key")
    p = await db.providers.find_one({"api_key_hash": _hash(key), "status": "active"}, {"_id": 0})
    if not p or not hmac.compare_digest(p["api_key_hash"], _hash(key)):
        raise HTTPException(status_code=401, detail="Invalid provider key")
    return p


async def get_session_user(provider: dict, token: str) -> tuple[dict, dict]:
    s = await db.game_sessions.find_one({"token": token, "provider_id": provider["id"]}, {"_id": 0})
    if not s or s["expires_at"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(status_code=401, detail="INVALID_SESSION")
    user = await db.users.find_one({"id": s["user_id"], "status": "active"}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=403, detail="PLAYER_BLOCKED")
    return s, user


async def _existing(provider: dict, tx_id: str) -> Optional[dict]:
    return await db.game_transactions.find_one({"provider_id": provider["id"], "external_tx_id": tx_id}, {"_id": 0})


def _dup(gtx: dict) -> dict:
    if gtx["status"] == "insufficient_funds":
        raise HTTPException(status_code=402, detail="INSUFFICIENT_FUNDS")
    if gtx["status"] == "processing":
        raise HTTPException(status_code=409, detail="PROCESSING_RETRY_LATER")
    return _reply(gtx, True)


def _reply(gtx: dict, duplicate: bool = False) -> dict:
    return {"status": gtx["status"], "transaction_id": gtx["external_tx_id"], "balance": gtx.get("balance_after"),
            "currency": "USD", "duplicate": duplicate}


async def _record(provider: dict, user: dict, kind: str, tx_id: str, round_id: str, amount: float,
                  game_code: Optional[str], extra: Optional[dict] = None) -> dict:
    gtx = {"id": new_id(), "provider_id": provider["id"], "provider_name": provider["name"], "user_id": user["id"],
           "user_email": user["email"], "type": kind, "external_tx_id": tx_id, "round_id": round_id,
           "game_code": game_code, "amount": round(amount, 2), "status": "processing", "created_at": now_iso(),
           **(extra or {})}
    await db.game_transactions.insert_one(gtx)
    gtx.pop("_id", None)
    return gtx


async def _finish(gtx: dict, user: dict, ledger_amount: float, desc: str) -> dict:
    updated = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    await db.game_transactions.update_one({"id": gtx["id"]}, {"$set": {"status": "ok", "balance_after": updated["promo_balance"]}})
    await db.transactions.insert_one(make_tx(updated, gtx["type"], "credit", ledger_amount, desc,
                                             gtx["round_id"], updated["promo_balance"]))
    return {**gtx, "status": "ok", "balance_after": updated["promo_balance"]}


@router.post("/provider/v1/balance")
async def pv_balance(body: SessionIn, provider: dict = Depends(get_provider)):
    _, user = await get_session_user(provider, body.session_token)
    return {"status": "ok", "player_id": user["id"], "balance": user.get("promo_balance", 0), "currency": "USD"}


@router.post("/provider/v1/bet")
async def pv_bet(body: BetIn, provider: dict = Depends(get_provider)):
    _, user = await get_session_user(provider, body.session_token)
    if ex := await _existing(provider, body.transaction_id):
        return _dup(ex)
    try:
        gtx = await _record(provider, user, "bet", body.transaction_id, body.round_id, body.amount, body.game_code)
    except DuplicateKeyError:
        return _dup(await _existing(provider, body.transaction_id))
    debited = await db.users.find_one_and_update({"id": user["id"], "promo_balance": {"$gte": body.amount}},
                                                 {"$inc": {"promo_balance": -round(body.amount, 2)}})
    if not debited:
        await db.game_transactions.update_one({"id": gtx["id"]}, {"$set": {"status": "insufficient_funds",
                                                                           "balance_after": user.get("promo_balance", 0)}})
        raise HTTPException(status_code=402, detail="INSUFFICIENT_FUNDS")
    gtx = await _finish(gtx, user, -body.amount, f"Bet · {provider['name']}" + (f" · {body.game_code}" if body.game_code else ""))
    return _reply(gtx)


@router.post("/provider/v1/win")
async def pv_win(body: WinIn, provider: dict = Depends(get_provider)):
    _, user = await get_session_user(provider, body.session_token)
    if ex := await _existing(provider, body.transaction_id):
        return _dup(ex)
    if not await db.game_transactions.find_one({"provider_id": provider["id"], "user_id": user["id"],
                                                "round_id": body.round_id, "type": "bet", "status": "ok",
                                                "rolled_back": {"$ne": True}}):
        raise HTTPException(status_code=400, detail="NO_BET_FOR_ROUND")
    try:
        gtx = await _record(provider, user, "win", body.transaction_id, body.round_id, body.amount, body.game_code)
    except DuplicateKeyError:
        return _dup(await _existing(provider, body.transaction_id))
    if body.amount > 0:
        await db.users.update_one({"id": user["id"]}, {"$inc": {"promo_balance": round(body.amount, 2)}})
    gtx = await _finish(gtx, user, body.amount, f"Win · {provider['name']}" + (f" · {body.game_code}" if body.game_code else ""))
    return _reply(gtx)


@router.post("/provider/v1/rollback")
async def pv_rollback(body: RollbackIn, provider: dict = Depends(get_provider)):
    _, user = await get_session_user(provider, body.session_token)
    if ex := await _existing(provider, body.transaction_id):
        return _dup(ex)
    bet = await db.game_transactions.find_one_and_update(
        {"provider_id": provider["id"], "user_id": user["id"], "external_tx_id": body.ref_transaction_id,
         "type": "bet", "status": "ok", "rolled_back": {"$ne": True}},
        {"$set": {"rolled_back": True}}, projection={"_id": 0})
    if not bet:
        raise HTTPException(status_code=404, detail="BET_NOT_FOUND_OR_ALREADY_ROLLED_BACK")
    try:
        gtx = await _record(provider, user, "rollback", body.transaction_id, bet["round_id"], bet["amount"], bet.get("game_code"),
                            {"ref_transaction_id": body.ref_transaction_id})
    except DuplicateKeyError:
        await db.game_transactions.update_one({"id": bet["id"]}, {"$set": {"rolled_back": False}})
        return _dup(await _existing(provider, body.transaction_id))
    await db.users.update_one({"id": user["id"]}, {"$inc": {"promo_balance": bet["amount"]}})
    gtx = await _finish(gtx, user, bet["amount"], f"Bet refund (rollback) · {provider['name']}")
    return _reply(gtx)


SEED_PROVIDERS = [
    ("Evolution", "evolution", "Live casino: roulette, blackjack, baccarat and game shows"),
    ("Ezugi", "ezugi", "Live dealer tables: Teen Patti, Andar Bahar, roulette"),
    ("Pragmatic Play", "pragmatic", "Slots and live casino"),
]


async def seed_providers() -> None:
    for name, code, desc in SEED_PROVIDERS:
        if not await db.providers.find_one({"code": code}):
            key = "pk_" + secrets.token_urlsafe(32)
            await db.providers.insert_one({"id": new_id(), "name": name, "code": code, "launch_url": None,
                                           "description": desc, "status": "active", "api_key_hash": _hash(key),
                                           "api_key_last4": key[-4:], "created_at": now_iso()})
