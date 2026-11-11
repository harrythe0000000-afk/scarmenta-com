from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import ReturnDocument

from core import db, get_current_user, get_settings, make_tx, new_id, now, now_iso, require_admin

router = APIRouter(prefix="/api")


class RunIn(BaseModel):
    start: str
    end: str


def _iso(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


async def _default_start() -> str:
    last = await db.loss_reward_runs.find_one({}, {"_id": 0, "period_end": 1}, sort=[("period_end", -1)])
    return last["period_end"] if last else (now() - timedelta(days=7)).isoformat()


async def _game_totals(match: dict) -> dict:
    rows = await db.game_transactions.aggregate([
        {"$match": {"status": "ok", **match}},
        {"$group": {"_id": {"u": "$user_id", "t": "$type"}, "sum": {"$sum": "$amount"}}}]).to_list(100000)
    out: dict = {}
    for r in rows:
        o = out.setdefault(r["_id"]["u"], {"bets": 0.0, "wins": 0.0, "rollbacks": 0.0})
        key = {"bet": "bets", "win": "wins", "rollback": "rollbacks"}.get(r["_id"]["t"])
        if key:
            o[key] += r["sum"]
    for o in out.values():
        o["net_loss"] = round(o["bets"] - o["rollbacks"] - o["wins"], 2)
    return out


async def _preview(start: str, end: str) -> dict:
    s = await get_settings()
    pct = s["loss_reward_percent"]
    totals = await _game_totals({"created_at": {"$gte": start, "$lt": end}})
    users = {u["id"]: u for u in await db.users.find({"id": {"$in": list(totals)}}, {"_id": 0, "id": 1, "email": 1, "name": 1}).to_list(100000)}
    rows = []
    for uid, t in totals.items():
        if t["net_loss"] > 0 and uid in users:
            rows.append({"user_id": uid, "email": users[uid]["email"], "name": users[uid]["name"], **t,
                         "reward": round(t["net_loss"] * pct / 100, 2)})
    rows.sort(key=lambda r: -r["net_loss"])
    return {"start": start, "end": end, "percent": pct, "rows": rows,
            "total_reward": round(sum(r["reward"] for r in rows), 2)}


@router.get("/admin/loss-rewards/preview")
async def preview(start: Optional[str] = None, end: Optional[str] = None, _: dict = Depends(require_admin)):
    return await _preview(_iso(start) if start else await _default_start(), _iso(end) if end else now_iso())


@router.post("/admin/loss-rewards/run")
async def run(body: RunIn, admin: dict = Depends(require_admin)):
    start, end = _iso(body.start), _iso(body.end)
    if start >= end or end > now_iso():
        raise HTTPException(status_code=400, detail="The period must end in the past and after it starts")
    if await db.loss_reward_runs.find_one({"period_start": {"$lt": end}, "period_end": {"$gt": start}}):
        raise HTTPException(status_code=400, detail="This period overlaps a previous payout")
    p = await _preview(start, end)
    if p["percent"] <= 0:
        raise HTTPException(status_code=400, detail="Loss reward % is 0 — set it in Credit Config first")
    if not p["rows"]:
        raise HTTPException(status_code=400, detail="No player had a net loss in this period")
    run_doc = {"id": new_id(), "period_start": start, "period_end": end, "percent": p["percent"],
               "players": len(p["rows"]), "total_reward": p["total_reward"], "paid_by": admin["email"],
               "created_at": now_iso()}
    await db.loss_reward_runs.insert_one(dict(run_doc))
    for r in p["rows"]:
        user = await db.users.find_one_and_update(
            {"id": r["user_id"]}, {"$inc": {"promo_balance": r["reward"], "loss_rewards_total": r["reward"]}},
            projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
        await db.transactions.insert_one(make_tx(
            user, "loss_reward", "credit", r["reward"],
            f"Weekly loss reward: {p['percent']:g}% of ${r['net_loss']:,.2f} net loss ({start[:10]} → {end[:10]})",
            f"LR-{run_doc['id'][:8].upper()}", user["promo_balance"]))
    return run_doc


@router.get("/admin/loss-rewards/runs")
async def runs(_: dict = Depends(require_admin)):
    return await db.loss_reward_runs.find({}, {"_id": 0}).sort("period_end", -1).to_list(200)


@router.get("/rewards/loss/me")
async def my_loss_rewards(user: dict = Depends(get_current_user)):
    s = await get_settings()
    start = await _default_start()
    t = (await _game_totals({"user_id": user["id"], "created_at": {"$gte": start}})).get(
        user["id"], {"bets": 0, "wins": 0, "rollbacks": 0, "net_loss": 0})
    history = await db.transactions.find({"user_id": user["id"], "type": "loss_reward"}, {"_id": 0}
                                         ).sort("created_at", -1).to_list(200)
    return {"percent": s["loss_reward_percent"], "period_start": start, **t,
            "estimated_reward": round(max(t["net_loss"], 0) * s["loss_reward_percent"] / 100, 2),
            "total_received": user.get("loss_rewards_total", 0), "history": history}


async def _sum(coll, match: dict, field: str) -> float:
    r = await db[coll].aggregate([{"$match": match}, {"$group": {"_id": None, "v": {"$sum": f"${field}"}}}]).to_list(1)
    return round(r[0]["v"], 2) if r else 0.0


@router.get("/admin/money-flow")
async def money_flow(_: dict = Depends(require_admin)):
    approved = {"status": "approved"}
    bets = await _sum("game_transactions", {"status": "ok", "type": "bet"}, "amount")
    wins = await _sum("game_transactions", {"status": "ok", "type": "win"}, "amount")
    refunds = await _sum("game_transactions", {"status": "ok", "type": "rollback"}, "amount")
    return {
        "cash_in": await _sum("deposits", approved, "amount"),
        "cash_in_usdt": await _sum("deposits", {**approved, "method": "usdt"}, "amount"),
        "cash_in_upi": await _sum("deposits", {**approved, "method": "upi"}, "amount"),
        "cash_in_upi_inr": await _sum("deposits", {**approved, "method": "upi"}, "local_amount"),
        "credits_issued": await _sum("deposits", approved, "promo_credit"),
        "referral_paid": await _sum("transactions", {"type": "referral_bonus"}, "amount"),
        "loss_rewards_paid": await _sum("transactions", {"type": "loss_reward"}, "amount"),
        "adjustments": await _sum("transactions", {"type": "admin_adjustment"}, "amount"),
        "bets": bets, "wins": wins, "refunds": refunds, "ggr": round(bets - refunds - wins, 2),
        "outstanding": await _sum("users", {"role": "user"}, "promo_balance"),
    }
