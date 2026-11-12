from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from core import db, site_url, get_current_user, get_settings, make_tx, now_iso, require_staff, unique_referral_code

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
async def share_visit(body: ShareVisitIn):
    ref = await db.users.find_one({"referral_code": body.code.strip().upper(), "role": "user"}, {"_id": 0, "id": 1})
    if ref:
        await db.share_visits.insert_one({"referrer_id": ref["id"], "source": "calc_share", "created_at": now_iso()})
    return {"ok": True}


@router.get("/share/me")
async def share_me(user: dict = Depends(get_current_user)):
    s = await get_settings()
    q = {"referred_by": user["id"], "signup_source": "calc_share"}
    return {"bonus_amount": s.get("share_bonus_amount", 0),
            "visits": await db.share_visits.count_documents({"referrer_id": user["id"]}),
            "signups": await db.users.count_documents(q),
            "deposited": await db.users.count_documents({**q, "share_bonus_paid": True}),
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
