import hashlib
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core import (client_ip, now, db, site_url, get_current_user, get_settings, make_tx, new_id, now_iso,
                  require_admin, require_staff, unique_referral_code)
from rewards import _mask

router = APIRouter(prefix="/api")


def mask_name(name: str) -> str:
    parts = (name or "").split()
    return " ".join(p[0] + "*" * max(len(p) - 1, 1) for p in parts) or "Player"


@router.get("/referrals/me")
async def my_referrals(request: Request, user: dict = Depends(get_current_user)):
    code = user.get("referral_code")
    if not code:
        code = await unique_referral_code()
        await db.users.update_one({"id": user["id"]}, {"$set": {"referral_code": code}})
    s = await get_settings()
    rows = await db.users.find({"referred_by": user["id"]},
                               {"_id": 0, "name": 1, "created_at": 1, "referral_rewarded": 1, "referral_reward": 1}
                               ).sort("created_at", -1).to_list(500)
    refs = [{"name": mask_name(r["name"]), "joined_at": r["created_at"],
             "status": "earning" if r.get("referral_rewarded") else "pending",
             "reward": r.get("referral_reward", 0)} for r in rows]
    return {"code": code, "link": f"{site_url(request)}/register?ref={code}", "bonus_percent": s["referral_bonus_percent"],
            "total_referred": len(refs), "total_earned": round(sum(r["reward"] for r in refs), 2), "referrals": refs}


async def reward_referrer(dep: dict) -> None:
    referee = await db.users.find_one({"id": dep["user_id"]}, {"_id": 0, "id": 1, "name": 1, "referred_by": 1})
    if not referee or not referee.get("referred_by"):
        return
    s = await get_settings()
    bonus = round(dep["amount"] * s["referral_bonus_percent"] / 100, 2)
    if bonus <= 0:
        return
    res = await db.deposits.update_one({"id": dep["id"], "referral_paid": {"$ne": True}},
                                       {"$set": {"referral_paid": True, "referral_bonus": bonus,
                                                 "referrer_id": referee["referred_by"]}})
    if not res.modified_count:
        return
    await db.users.update_one({"id": referee["id"]}, {"$inc": {"referral_reward": bonus},
                                                      "$set": {"referral_rewarded": True, "referral_rewarded_at": now_iso()}})
    referrer = await db.users.find_one_and_update(
        {"id": referee["referred_by"]}, {"$inc": {"promo_balance": bonus, "referral_earnings": bonus}},
        projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    if referrer:
        await db.transactions.insert_one(make_tx(
            referrer, "referral_bonus", "credit", bonus,
            f"Referral income: {s['referral_bonus_percent']:g}% of {mask_name(referee['name'])}'s ${dep['amount']:,.2f} deposit",
            dep["reference"], referrer["promo_balance"]))


class ShareVisitIn(BaseModel):
    code: str = Field(min_length=3, max_length=20)


@router.post("/share/visit")
async def share_visit(body: ShareVisitIn, request: Request):
    ref = await db.users.find_one({"referral_code": body.code.strip().upper(), "role": "user"}, {"_id": 0, "id": 1})
    if ref:
        ip = hashlib.sha256(client_ip(request).encode()).hexdigest()[:24]
        day = (now() - timedelta(hours=24)).isoformat()
        await db.share_visits.update_one({"referrer_id": ref["id"], "ip_hash": ip, "created_at": {"$gt": day}},
                                         {"$setOnInsert": {"referrer_id": ref["id"], "ip_hash": ip, "source": "calc_share",
                                                           "created_at": now_iso()}}, upsert=True)
    return {"ok": True}


@router.get("/share/me")
async def share_me(user: dict = Depends(get_current_user)):
    s = await get_settings()
    q = {"referred_by": user["id"], "signup_source": "calc_share"}
    return {"bonus_amount": s.get("share_bonus_amount", 0),
            "visits": await db.share_visits.count_documents({"referrer_id": user["id"]}),
            "signups": await db.users.count_documents(q),
            "deposited": len(await db.deposits.distinct("user_id", {
                "status": "approved", "user_id": {"$in": await db.users.distinct("id", q)}})),
            "earned": round(user.get("share_earnings", 0), 2)}


async def reward_share(dep: dict) -> None:
    s = await get_settings()
    bonus = round(float(s.get("share_bonus_amount", 0)), 2)
    if bonus <= 0:
        return
    referee = await db.users.find_one_and_update(
        {"id": dep["user_id"], "signup_source": "calc_share", "referred_by": {"$ne": None}, "share_bonus_paid": {"$ne": True}},
        {"$set": {"share_bonus_paid": True, "share_bonus": bonus, "share_bonus_at": now_iso()}},
        projection={"_id": 0, "name": 1, "referred_by": 1})
    if not referee:
        return
    referrer = await db.users.find_one_and_update(
        {"id": referee["referred_by"]}, {"$inc": {"promo_balance": bonus, "share_earnings": bonus}},
        projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    if referrer:
        await db.transactions.insert_one(make_tx(
            referrer, "share_bonus", "credit", bonus,
            f"Share bonus: {mask_name(referee['name'])} joined from your calculator image and made a first deposit",
            dep["reference"], referrer["promo_balance"]))


@router.get("/admin/referrals")
async def admin_referrals(status: Optional[str] = None, _: dict = Depends(require_staff)):
    q: dict = {"referred_by": {"$ne": None}}
    if status == "earning":
        q["referral_rewarded"] = True
    elif status == "pending":
        q["referral_rewarded"] = {"$ne": True}
    rows = await db.users.find(q, {"_id": 0, "id": 1, "name": 1, "email": 1, "created_at": 1, "referred_by_email": 1,
                                   "referral_rewarded": 1, "referral_reward": 1}).sort("created_at", -1).to_list(1000)
    return [{**r, "status": "earning" if r.get("referral_rewarded") else "pending",
             "reward": r.get("referral_reward", 0)} for r in rows]


async def _top_sharers(limit: int = 10) -> tuple:
    since = (now() - timedelta(days=7)).isoformat()
    rows = await db.users.aggregate([
        {"$match": {"signup_source": "calc_share", "referred_by": {"$ne": None}, "created_at": {"$gte": since}}},
        {"$group": {"_id": "$referred_by", "friends": {"$sum": 1}, "first": {"$min": "$created_at"}}},
        {"$sort": {"friends": -1, "first": 1}}]).to_list(100000)
    users = {u["id"]: u for u in await db.users.find({"id": {"$in": [r["_id"] for r in rows]}, "role": "user"},
                                                     {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(100000)}
    ranked = [{"user_id": r["_id"], "friends": r["friends"], "name": users[r["_id"]]["name"],
               "email": users[r["_id"]]["email"]} for r in rows if r["_id"] in users]
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    return since, ranked


@router.get("/leaderboard/sharers")
async def sharer_leaderboard(user: dict = Depends(get_current_user)):
    since, ranked = await _top_sharers()
    mine = next((r for r in ranked if r["user_id"] == user["id"]), None)
    return {"start": since, "end": now_iso(), "players": len(ranked),
            "top": [{"rank": r["rank"], "name": _mask(r["name"]), "friends": r["friends"],
                     "is_me": r["user_id"] == user["id"]} for r in ranked[:10]],
            "me": {"rank": mine["rank"], "friends": mine["friends"]} if mine else None}


class SharerRewardIn(BaseModel):
    amounts: List[float] = Field(min_length=1, max_length=3)


@router.get("/admin/sharers")
async def admin_sharers(_: dict = Depends(require_admin)):
    since, ranked = await _top_sharers()
    runs = await db.sharer_reward_runs.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"start": since, "end": now_iso(), "top": ranked[:10], "runs": runs}


@router.post("/admin/sharers/reward")
async def reward_sharers(body: SharerRewardIn, admin: dict = Depends(require_admin)):
    if any(a < 0 or a > 10000 for a in body.amounts) or not any(a > 0 for a in body.amounts):
        raise HTTPException(status_code=400, detail="Enter bonus amounts between $0 and $10,000")
    try:
        await db.locks.insert_one({"_id": "sharer_reward", "at": now_iso()})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A reward is already being sent. Please wait.")
    try:
        last = await db.sharer_reward_runs.find_one({}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
        if last and last["created_at"] > (now() - timedelta(days=7)).isoformat():
            raise HTTPException(status_code=400, detail="Top sharers were already rewarded in the last 7 days")
        since, ranked = await _top_sharers()
        if not ranked:
            raise HTTPException(status_code=400, detail="No sharers to reward this week")
        if not any(a > 0 for a in body.amounts[:len(ranked)]):
            raise HTTPException(status_code=400, detail="Enter an amount for at least one ranked sharer")
        run_id, winners = new_id(), []
        for r, amt in zip(ranked, body.amounts):
            amt = round(amt, 2)
            if amt <= 0:
                continue
            u = await db.users.find_one_and_update({"id": r["user_id"]}, {"$inc": {"promo_balance": amt}},
                                                   projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
            if not u:
                continue
            await db.transactions.insert_one(make_tx(u, "sharer_reward", "credit", amt,
                                                     f"Top sharer #{r['rank']} this week ({r['friends']} friends joined)",
                                                     run_id, u["promo_balance"]))
            winners.append({"rank": r["rank"], "user_id": u["id"], "name": u["name"], "email": u["email"],
                            "friends": r["friends"], "amount": amt})
        if not winners:
            raise HTTPException(status_code=400, detail="No one was paid. Enter an amount for at least one ranked sharer")
        run = {"id": run_id, "period_start": since, "period_end": now_iso(), "winners": winners,
               "total": round(sum(w["amount"] for w in winners), 2), "created_by": admin["email"], "created_at": now_iso()}
        await db.sharer_reward_runs.insert_one(dict(run))
        return run
    finally:
        await db.locks.delete_one({"_id": "sharer_reward"})
