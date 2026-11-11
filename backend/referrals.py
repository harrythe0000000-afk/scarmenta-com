from typing import Optional

from fastapi import APIRouter, Depends
from pymongo import ReturnDocument

from core import FRONTEND_URL, db, get_current_user, get_settings, make_tx, now_iso, require_admin, unique_referral_code

router = APIRouter(prefix="/api")


def mask_name(name: str) -> str:
    parts = (name or "").split()
    return " ".join(p[0] + "*" * max(len(p) - 1, 1) for p in parts) or "Player"


@router.get("/referrals/me")
async def my_referrals(user: dict = Depends(get_current_user)):
    code = user.get("referral_code")
    if not code:
        code = await unique_referral_code()
        await db.users.update_one({"id": user["id"]}, {"$set": {"referral_code": code}})
    s = await get_settings()
    rows = await db.users.find({"referred_by": user["id"]},
                               {"_id": 0, "name": 1, "created_at": 1, "referral_rewarded": 1, "referral_reward": 1}
                               ).sort("created_at", -1).to_list(500)
    refs = [{"name": mask_name(r["name"]), "joined_at": r["created_at"],
             "status": "rewarded" if r.get("referral_rewarded") else "pending",
             "reward": r.get("referral_reward", 0)} for r in rows]
    return {"code": code, "link": f"{FRONTEND_URL}/register?ref={code}", "bonus_percent": s["referral_bonus_percent"],
            "total_referred": len(refs), "total_earned": round(sum(r["reward"] for r in refs), 2), "referrals": refs}


async def reward_referrer(dep: dict) -> None:
    referee = await db.users.find_one_and_update(
        {"id": dep["user_id"], "referred_by": {"$ne": None}, "referral_rewarded": {"$ne": True}},
        {"$set": {"referral_rewarded": True, "referral_rewarded_at": now_iso()}},
        projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    if not referee:
        return
    s = await get_settings()
    bonus = round(dep["amount"] * s["referral_bonus_percent"] / 100, 2)
    await db.users.update_one({"id": referee["id"]}, {"$set": {"referral_reward": bonus}})
    if bonus <= 0:
        return
    referrer = await db.users.find_one_and_update(
        {"id": referee["referred_by"]}, {"$inc": {"promo_balance": bonus}},
        projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    if referrer:
        await db.transactions.insert_one(make_tx(
            referrer, "referral_bonus", "credit", bonus,
            f"Refer & earn: {s['referral_bonus_percent']:g}% of {mask_name(referee['name'])}'s first deposit",
            dep["reference"], referrer["promo_balance"]))


@router.get("/admin/referrals")
async def admin_referrals(status: Optional[str] = None, _: dict = Depends(require_admin)):
    q: dict = {"referred_by": {"$ne": None}}
    if status == "rewarded":
        q["referral_rewarded"] = True
    elif status == "pending":
        q["referral_rewarded"] = {"$ne": True}
    rows = await db.users.find(q, {"_id": 0, "id": 1, "name": 1, "email": 1, "created_at": 1, "referred_by_email": 1,
                                   "referral_rewarded": 1, "referral_reward": 1}).sort("created_at", -1).to_list(1000)
    return [{**r, "status": "rewarded" if r.get("referral_rewarded") else "pending",
             "reward": r.get("referral_reward", 0)} for r in rows]
