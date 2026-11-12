import secrets
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from pymongo import ReturnDocument

from core import (clean, db, get_current_user, hash_password, new_id, now_iso, require_admin, require_staff,
                  site_url)
from referrals import mask_name

router = APIRouter(prefix="/api")


class AgentIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    commission_percent: Optional[float] = Field(default=None, ge=0, le=50)


TIERS = [(10, 5.0), (50, 7.0), (None, 10.0)]
TIER_TEXT = "1–10 players: 5% · 11–50 players: 7% · 51+ players: 10%"


def tier_rate(players: int) -> float:
    for limit, rate in TIERS:
        if limit is None or players <= limit:
            return rate


class AgentUpdateIn(BaseModel):
    commission_percent: Optional[float] = Field(default=None, ge=0, le=50)
    status: Optional[Literal["active", "suspended"]] = None


class PayoutIn(BaseModel):
    note: str = Field(default="", max_length=200)


async def _code() -> str:
    while True:
        code = "AG" + secrets.token_hex(3).upper()
        if not await db.users.find_one({"agent_code": code}):
            return code


async def _stats(agent_ids: list) -> dict:
    rows = await db.agent_commissions.aggregate([
        {"$match": {"agent_id": {"$in": agent_ids}}},
        {"$group": {"_id": {"a": "$agent_id", "s": "$status"}, "sum": {"$sum": "$amount"},
                    "vol": {"$sum": "$deposit_amount"}}}]).to_list(10000)
    players = await db.users.aggregate([
        {"$match": {"agent_id": {"$in": agent_ids}}}, {"$group": {"_id": "$agent_id", "n": {"$sum": 1}}}]).to_list(10000)
    out = {a: {"players": 0, "volume": 0.0, "earned": 0.0, "unpaid": 0.0, "paid": 0.0} for a in agent_ids}
    for p in players:
        out[p["_id"]]["players"] = p["n"]
    for r in rows:
        o = out[r["_id"]["a"]]
        o["volume"] += r["vol"]
        o["earned"] += r["sum"]
        o["unpaid" if r["_id"]["s"] == "unpaid" else "paid"] += r["sum"]
    return {a: {k: round(v, 2) for k, v in o.items()} for a, o in out.items()}


async def reward_agent(dep: dict) -> None:
    player = await db.users.find_one({"id": dep["user_id"]}, {"_id": 0, "agent_id": 1, "name": 1})
    if not player or not player.get("agent_id"):
        return
    agent = await db.users.find_one({"id": player["agent_id"], "role": "agent", "status": "active"}, {"_id": 0})
    if not agent:
        return
    rate = tier_rate(await db.users.count_documents({"agent_id": agent["id"]}))
    amount = round(dep["amount"] * rate / 100, 2)
    res = await db.deposits.update_one({"id": dep["id"], "agent_commission_done": {"$ne": True}},
                                       {"$set": {"agent_commission_done": True, "agent_id": agent["id"]}})
    if not res.modified_count or amount <= 0:
        return
    await db.agent_commissions.insert_one({
        "id": new_id(), "agent_id": agent["id"], "player_id": dep["user_id"], "player_name": mask_name(player["name"]),
        "deposit_ref": dep["reference"], "deposit_amount": dep["amount"], "percent": rate,
        "amount": amount, "status": "unpaid", "created_at": now_iso()})


# ---------- Owner / staff ----------
@router.get("/admin/agents")
async def list_agents(_: dict = Depends(require_staff)):
    agents = await db.users.find({"role": "agent"}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)
    stats = await _stats([a["id"] for a in agents])
    return [{**a, **stats[a["id"]], "current_rate": tier_rate(stats[a["id"]]["players"])} for a in agents]


@router.post("/admin/agents")
async def create_agent(body: AgentIn, admin: dict = Depends(require_admin)):
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Name cannot be blank")
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    agent = {"id": new_id(), "email": email, "name": body.name.strip(), "password_hash": hash_password(body.password),
             "role": "agent", "status": "active", "email_verified": True, "promo_balance": 0.0,
             "agent_code": await _code(), "commission_percent": None,
             "created_by": admin["email"], "created_at": now_iso()}
    await db.users.insert_one(agent)
    return clean(agent)


@router.patch("/admin/agents/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdateIn, _: dict = Depends(require_admin)):
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Nothing to update")
    a = await db.users.find_one_and_update({"id": agent_id, "role": "agent"}, {"$set": changes},
                                           projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    return a


@router.post("/admin/agents/{agent_id}/payout")
async def payout(agent_id: str, body: PayoutIn, admin: dict = Depends(require_admin)):
    if not await db.users.find_one({"id": agent_id, "role": "agent"}):
        raise HTTPException(status_code=404, detail="Agent not found")
    if not await db.agent_commissions.count_documents({"agent_id": agent_id, "status": "unpaid"}):
        raise HTTPException(status_code=400, detail="No unpaid commission for this agent")
    pid = new_id()
    await db.agent_commissions.update_many({"agent_id": agent_id, "status": "unpaid"},
                                           {"$set": {"status": "paid", "payout_id": pid, "paid_at": now_iso()}})
    rows = await db.agent_commissions.find({"payout_id": pid}, {"_id": 0, "amount": 1}).to_list(100000)
    if not rows:
        raise HTTPException(status_code=400, detail="No unpaid commission for this agent")
    doc = {"id": pid, "agent_id": agent_id, "amount": round(sum(r["amount"] for r in rows), 2), "count": len(rows),
           "note": body.note, "paid_by": admin["email"], "created_at": now_iso()}
    await db.agent_payouts.insert_one(dict(doc))
    return doc


@router.get("/admin/agents/{agent_id}/commissions")
async def agent_commissions(agent_id: str, _: dict = Depends(require_staff)):
    return await db.agent_commissions.find({"agent_id": agent_id}, {"_id": 0}).sort("created_at", -1).to_list(1000)


# ---------- Agent portal ----------
async def require_agent(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "agent":
        raise HTTPException(status_code=403, detail="Agent access required")
    return user


@router.get("/agent/me")
async def agent_me(request: Request, agent: dict = Depends(require_agent)):
    players = await db.users.find({"agent_id": agent["id"]}, {"_id": 0, "id": 1, "name": 1, "created_at": 1}
                                  ).sort("created_at", -1).to_list(1000)
    vol = {r["_id"]: r["v"] for r in await db.deposits.aggregate([
        {"$match": {"user_id": {"$in": [p["id"] for p in players]}, "status": "approved"}},
        {"$group": {"_id": "$user_id", "v": {"$sum": "$amount"}}}]).to_list(10000)}
    return {
        "name": agent["name"], "code": agent["agent_code"], "commission_percent": tier_rate(len(players)), "tiers": TIER_TEXT,
        "link": f"{site_url(request)}/register?agent={agent['agent_code']}",
        **(await _stats([agent["id"]]))[agent["id"]],
        "players_list": [{"name": mask_name(p["name"]), "joined_at": p["created_at"], "deposited": round(vol.get(p["id"], 0), 2)}
                         for p in players],
        "commissions": await db.agent_commissions.find({"agent_id": agent["id"]}, {"_id": 0, "player_id": 0}
                                                      ).sort("created_at", -1).to_list(500),
        "payouts": await db.agent_payouts.find({"agent_id": agent["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200),
    }
