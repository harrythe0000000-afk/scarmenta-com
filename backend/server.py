from core import (db, client, now, now_iso, new_id, clean, hash_password, verify_password, set_auth_cookies,
                  set_access_cookie, clear_auth_cookies, decode_token, get_current_user, require_admin,
                  get_settings, compute_breakdown, client_ip, DEFAULT_SETTINGS, FRONTEND_URL)
from emailer import send_verification_email, send_reset_email

import asyncio
import logging
import os
import re
import secrets
from contextlib import suppress
from datetime import timedelta, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument
from starlette.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

INDEXES: dict[str, list[IndexModel]] = {
    "users": [IndexModel([("email", ASCENDING)], name="email", unique=True),
              IndexModel([("id", ASCENDING)], name="id", unique=True)],
    "deposits": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                 IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created"),
                 IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created")],
    "transactions": [IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created"),
                     IndexModel([("created_at", DESCENDING)], name="created_desc")],
    "tickets": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                IndexModel([("user_id", ASCENDING), ("updated_at", DESCENDING)], name="user_updated")],
    "fraud_alerts": [IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created")],
    "login_attempts": [IndexModel([("identifier", ASCENDING)], name="identifier")],
    "email_tokens": [IndexModel([("token", ASCENDING)], name="token", unique=True),
                     IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=0)],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)


app = FastAPI()
api = APIRouter(prefix="/api")

METHODS = Literal["upi", "netbanking", "card", "aed_wire", "usdt"]


# ---------- Models ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    country: Optional[str] = Field(default=None, max_length=60)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenIn(BaseModel):
    token: str


class EmailIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class DepositIn(BaseModel):
    amount: float = Field(gt=0)
    method: METHODS


class TicketIn(BaseModel):
    subject: str = Field(min_length=3, max_length=120)
    category: Literal["deposit", "wallet", "account", "technical", "other"]
    message: str = Field(min_length=5, max_length=2000)


class ReplyIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class UserStatusIn(BaseModel):
    status: Literal["active", "suspended"]


class AdjustIn(BaseModel):
    amount: float
    reason: str = Field(min_length=3, max_length=200)


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=300)


class TicketStatusIn(BaseModel):
    status: Literal["open", "resolved", "closed"]


class SettingsIn(BaseModel):
    promo_multiplier: float = Field(ge=1, le=10)
    min_deposit: float = Field(gt=0)
    max_deposit: float = Field(gt=0)
    fraud_amount_threshold: float = Field(gt=0)
    fraud_velocity_count: int = Field(ge=1, le=50)
    packages: List[float] = Field(min_length=1, max_length=8)


# ---------- Helpers ----------
def make_tx(user: dict, kind: str, wallet: str, amount: float, description: str, reference: str, balance_after: float) -> dict:
    return {"id": new_id(), "user_id": user["id"], "user_email": user["email"], "user_name": user.get("name", ""),
            "type": kind, "wallet": wallet, "amount": round(amount, 2), "description": description,
            "reference": reference, "balance_after": round(balance_after, 2), "created_at": now_iso()}


async def credit_deposit(dep: dict) -> None:
    user = await db.users.find_one_and_update(
        {"id": dep["user_id"]},
        {"$inc": {"promo_balance": dep["promo_credit"]}},
        projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    desc = f"₹{dep['amount']:,.0f} deposit via {dep['method'].upper()} · {dep['promo_multiplier']:g}X credit allocation"
    await db.transactions.insert_one(make_tx(user, "deposit", "credit", dep["promo_credit"], desc, dep["reference"],
                                             user["promo_balance"]))


async def add_alert(kind: str, severity: str, message: str, user: Optional[dict] = None, reference: str = "") -> None:
    await db.fraud_alerts.insert_one({
        "id": new_id(), "kind": kind, "severity": severity, "message": message,
        "user_id": user["id"] if user else None, "user_email": user["email"] if user else None,
        "reference": reference, "status": "open", "created_at": now_iso()})


async def issue_token(user: dict, kind: str, hours: int) -> str:
    token = secrets.token_urlsafe(32)
    await db.email_tokens.insert_one({"token": token, "user_id": user["id"], "kind": kind, "used": False,
                                      "created_at": now_iso(), "expires_at": now() + timedelta(hours=hours)})
    return token


async def consume_token(token: str, kind: str) -> dict:
    doc = await db.email_tokens.find_one({"token": token, "kind": kind})
    if not doc or doc.get("used") or doc["expires_at"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(status_code=400, detail="This link is invalid or has expired")
    await db.email_tokens.update_one({"token": token}, {"$set": {"used": True}})
    return doc


async def send_verification(user: dict) -> bool:
    token = await issue_token(user, "verify", 24)
    try:
        await send_verification_email(user, token)
        return True
    except Exception as exc:
        logger.error("verification email failed for %s: %s", user["email"], exc)
        return False


# ---------- Auth ----------
@api.post("/auth/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    user = {"id": new_id(), "email": email, "name": body.name.strip(), "country": body.country,
            "password_hash": hash_password(body.password), "role": "user", "status": "active",
            "email_verified": False, "real_balance": 0.0, "promo_balance": 0.0, "created_at": now_iso()}
    await db.users.insert_one(user)
    sent = await send_verification(user)
    set_auth_cookies(response, user)
    return {**clean(user), "verification_sent": sent}


@api.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.lower()
    ident = f"email:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("locked_until") and att["locked_until"] > now_iso():
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        count = (att or {}).get("count", 0) + 1
        update = {"count": count, "updated_at": now_iso()}
        if count >= 5:
            update = {"count": 0, "locked_until": (now() + timedelta(minutes=15)).isoformat()}
            await add_alert("login_lockout", "medium", f"5 failed login attempts for {email} (last from {client_ip(request)})",
                            clean(dict(user)) if user else None)
        await db.login_attempts.update_one({"identifier": ident}, {"$set": update}, upsert=True)
        if count >= 5:
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("status") == "suspended":
        raise HTTPException(status_code=403, detail="Account suspended. Contact support.")
    await db.login_attempts.delete_one({"identifier": ident})
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login_at": now_iso(), "last_ip": client_ip(request)}})
    set_auth_cookies(response, user)
    return clean(user)


@api.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    payload = decode_token(token, "refresh")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user or user.get("status") == "suspended":
        raise HTTPException(status_code=401, detail="User not found")
    set_access_cookie(response, user)
    return {"ok": True}


@api.post("/auth/verify-email")
async def verify_email(body: TokenIn):
    doc = await consume_token(body.token, "verify")
    await db.users.update_one({"id": doc["user_id"]}, {"$set": {"email_verified": True, "verified_at": now_iso()}})
    return {"ok": True}


@api.post("/auth/resend-verification")
async def resend_verification(user: dict = Depends(get_current_user)):
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email already verified")
    since = (now() - timedelta(seconds=60)).isoformat()
    if await db.email_tokens.find_one({"user_id": user["id"], "kind": "verify", "created_at": {"$gte": since}}):
        raise HTTPException(status_code=429, detail="Please wait a minute before requesting another email")
    if not await send_verification(user):
        raise HTTPException(status_code=502, detail="Could not send email right now. Try again shortly.")
    return {"ok": True}


@api.post("/auth/forgot-password")
async def forgot_password(body: EmailIn):
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0, "password_hash": 0})
    if user:
        token = await issue_token(user, "reset", 1)
        try:
            await send_reset_email(user, token)
        except Exception as exc:
            logger.error("reset email failed: %s", exc)
    return {"ok": True}


@api.post("/auth/reset-password")
async def reset_password(body: ResetIn):
    doc = await consume_token(body.token, "reset")
    await db.users.update_one({"id": doc["user_id"]}, {"$set": {"password_hash": hash_password(body.password)}})
    return {"ok": True}


# ---------- Public ----------
@api.get("/public/config")
async def public_config():
    s = await get_settings()
    return {k: s[k] for k in ("promo_multiplier", "min_deposit", "max_deposit", "packages")}


# ---------- User ----------
@api.get("/wallet")
async def wallet(user: dict = Depends(get_current_user)):
    agg = await db.deposits.aggregate([
        {"$match": {"user_id": user["id"], "status": "approved"}},
        {"$group": {"_id": None, "deposited": {"$sum": "$amount"}, "credits": {"$sum": "$promo_credit"},
                    "count": {"$sum": 1}}}]).to_list(1)
    totals = agg[0] if agg else {"deposited": 0, "credits": 0, "count": 0}
    pending = await db.deposits.count_documents({"user_id": user["id"], "status": "pending"})
    return {"balance": user.get("promo_balance", 0), "total_deposited": totals["deposited"],
            "total_credits": totals["credits"], "approved_count": totals["count"], "pending_count": pending}


@api.post("/deposits")
async def create_deposit(body: DepositIn, user: dict = Depends(get_current_user)):
    if user.get("role") != "user":
        raise HTTPException(status_code=403, detail="Only player accounts can deposit")
    if not user.get("email_verified"):
        raise HTTPException(status_code=403, detail="Please verify your email before making a deposit")
    s = await get_settings()
    if body.amount < s["min_deposit"] or body.amount > s["max_deposit"]:
        raise HTTPException(status_code=400, detail=f"Deposit must be between ₹{s['min_deposit']:,.0f} and ₹{s['max_deposit']:,.0f}")
    since = (now() - timedelta(hours=24)).isoformat()
    recent = await db.deposits.count_documents({"user_id": user["id"], "created_at": {"$gte": since}})
    flags = []
    if body.amount >= s["fraud_amount_threshold"]:
        flags.append("high_amount")
    if recent + 1 >= s["fraud_velocity_count"]:
        flags.append("velocity")
    dep = {"id": new_id(), "reference": f"DEP-{secrets.token_hex(4).upper()}", "user_id": user["id"],
           "user_email": user["email"], "user_name": user["name"], "amount": round(body.amount, 2), "currency": "INR",
           "method": body.method, **compute_breakdown(body.amount, s), "status": "pending", "fraud_flags": flags,
           "risk_score": min(100, 12 + 38 * len(flags)), "created_at": now_iso()}
    await db.deposits.insert_one(dep)
    if "high_amount" in flags:
        await add_alert("high_amount", "high", f"Deposit {dep['reference']} of ₹{body.amount:,.0f} exceeds threshold", user, dep["reference"])
    if "velocity" in flags:
        await add_alert("velocity", "medium", f"{recent + 1} deposits in 24h by {user['email']}", user, dep["reference"])
    return clean(dep)


@api.get("/deposits")
async def my_deposits(user: dict = Depends(get_current_user)):
    return await db.deposits.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)


def tx_query(base: dict, type_: Optional[str], wallet_: Optional[str], start: Optional[str], end: Optional[str]) -> dict:
    q = dict(base)
    if type_:
        q["type"] = type_
    if wallet_:
        q["wallet"] = wallet_
    if start or end:
        q["created_at"] = {}
        if start:
            q["created_at"]["$gte"] = start
        if end:
            q["created_at"]["$lte"] = end + "T23:59:59.999999+00:00"
    return q


@api.get("/transactions")
async def my_transactions(type: Optional[str] = None, wallet: Optional[str] = None, start: Optional[str] = None,
                          end: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = tx_query({"user_id": user["id"]}, type, wallet, start, end)
    return await db.transactions.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.post("/support/tickets")
async def create_ticket(body: TicketIn, user: dict = Depends(get_current_user)):
    t = {"id": new_id(), "reference": f"TCK-{secrets.token_hex(3).upper()}", "user_id": user["id"],
         "user_email": user["email"], "user_name": user["name"], "subject": body.subject, "category": body.category,
         "status": "open", "messages": [{"author_role": "user", "author_name": user["name"], "message": body.message,
                                         "created_at": now_iso()}], "created_at": now_iso(), "updated_at": now_iso()}
    await db.tickets.insert_one(t)
    return clean(t)


@api.get("/support/tickets")
async def my_tickets(user: dict = Depends(get_current_user)):
    return await db.tickets.find({"user_id": user["id"]}, {"_id": 0}).sort("updated_at", -1).to_list(200)


async def append_reply(ticket_id: str, user: dict, message: str, base_filter: dict) -> dict:
    msg = {"author_role": user["role"], "author_name": user["name"], "message": message, "created_at": now_iso()}
    t = await db.tickets.find_one_and_update(
        {"id": ticket_id, **base_filter},
        {"$push": {"messages": msg}, "$set": {"updated_at": now_iso(), **({"status": "open"} if user["role"] == "user" else {})}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t


@api.post("/support/tickets/{ticket_id}/reply")
async def reply_ticket(ticket_id: str, body: ReplyIn, user: dict = Depends(get_current_user)):
    return await append_reply(ticket_id, user, body.message, {"user_id": user["id"]})


# ---------- Admin ----------
@api.get("/admin/stats")
async def admin_stats(_: dict = Depends(require_admin)):
    agg = await db.deposits.aggregate([
        {"$match": {"status": "approved"}},
        {"$group": {"_id": None, "deposits": {"$sum": "$amount"}, "credits": {"$sum": "$promo_credit"},
                    "count": {"$sum": 1}}}]).to_list(1)
    t = agg[0] if agg else {"deposits": 0, "credits": 0, "count": 0}
    bal = await db.users.aggregate([
        {"$match": {"role": "user"}},
        {"$group": {"_id": None, "credits": {"$sum": "$promo_balance"}}}]).to_list(1)
    since_day = (now() - timedelta(days=29)).date()
    rows = await db.deposits.find({"status": "approved", "reviewed_at": {"$gte": since_day.isoformat()}},
                                  {"_id": 0, "amount": 1, "promo_credit": 1, "reviewed_at": 1}).to_list(10000)
    buckets = {(since_day + timedelta(days=i)).isoformat(): {"deposits": 0, "credits": 0} for i in range(30)}
    for r in rows:
        d = buckets.get(r["reviewed_at"][:10])
        if d:
            d["deposits"] += r["amount"]
            d["credits"] += r["promo_credit"]
    return {
        "total_deposits": t["deposits"], "total_credits": t["credits"], "approved_count": t["count"],
        "pending_count": await db.deposits.count_documents({"status": "pending"}),
        "users_count": await db.users.count_documents({"role": "user"}),
        "verified_users": await db.users.count_documents({"role": "user", "email_verified": True}),
        "open_alerts": await db.fraud_alerts.count_documents({"status": "open"}),
        "open_tickets": await db.tickets.count_documents({"status": "open"}),
        "credit_outstanding": bal[0]["credits"] if bal else 0,
        "series": [{"date": k, **v} for k, v in buckets.items()],
    }


@api.get("/admin/users")
async def admin_users(q: Optional[str] = None, _: dict = Depends(require_admin)):
    query: dict = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"email": rx}, {"name": rx}]
    return await db.users.find(query, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)


@api.patch("/admin/users/{user_id}/status")
async def admin_user_status(user_id: str, body: UserStatusIn, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot change your own status")
    res = await db.users.update_one({"id": user_id}, {"$set": {"status": body.status}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@api.post("/admin/users/{user_id}/adjust")
async def admin_adjust(user_id: str, body: AdjustIn, admin: dict = Depends(require_admin)):
    if body.amount == 0:
        raise HTTPException(status_code=400, detail="Amount cannot be zero")
    field = "promo_balance"
    flt = {"id": user_id, "role": "user"}
    if body.amount < 0:
        flt[field] = {"$gte": -body.amount}
    user = await db.users.find_one_and_update(flt, {"$inc": {field: round(body.amount, 2)}},
                                              projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    if not user:
        raise HTTPException(status_code=400, detail="User not found or insufficient balance")
    ref = f"ADJ-{secrets.token_hex(3).upper()}"
    await db.transactions.insert_one(make_tx(user, "admin_adjustment", "credit", body.amount,
                                             f"Admin adjustment: {body.reason} (by {admin['email']})", ref, user[field]))
    return user


@api.get("/admin/deposits")
async def admin_deposits(status: Optional[str] = None, _: dict = Depends(require_admin)):
    q = {"status": status} if status and status != "all" else {}
    return await db.deposits.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.post("/admin/deposits/{dep_id}/approve")
async def admin_approve(dep_id: str, admin: dict = Depends(require_admin)):
    dep = await db.deposits.find_one_and_update(
        {"id": dep_id, "status": "pending"},
        {"$set": {"status": "approved", "reviewed_at": now_iso(), "reviewed_by": admin["email"]}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not dep:
        raise HTTPException(status_code=409, detail="Deposit not found or already reviewed")
    await credit_deposit(dep)
    return dep


@api.post("/admin/deposits/{dep_id}/reject")
async def admin_reject(dep_id: str, body: RejectIn, admin: dict = Depends(require_admin)):
    dep = await db.deposits.find_one_and_update(
        {"id": dep_id, "status": "pending"},
        {"$set": {"status": "rejected", "reviewed_at": now_iso(), "reviewed_by": admin["email"],
                  "reject_reason": body.reason}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not dep:
        raise HTTPException(status_code=409, detail="Deposit not found or already reviewed")
    return dep


@api.get("/admin/transactions")
async def admin_transactions(q: Optional[str] = None, type: Optional[str] = None, wallet: Optional[str] = None,
                             start: Optional[str] = None, end: Optional[str] = None, _: dict = Depends(require_admin)):
    query = tx_query({}, type, wallet, start, end)
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"user_email": rx}, {"reference": rx}, {"description": rx}]
    return await db.transactions.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.get("/admin/settings")
async def admin_get_settings(_: dict = Depends(require_admin)):
    return await get_settings()


@api.put("/admin/settings")
async def admin_put_settings(body: SettingsIn, admin: dict = Depends(require_admin)):
    if body.min_deposit >= body.max_deposit:
        raise HTTPException(status_code=400, detail="Minimum deposit must be lower than maximum")
    if any(p < body.min_deposit or p > body.max_deposit for p in body.packages):
        raise HTTPException(status_code=400, detail="Every package must be within the min/max deposit limits")
    data = body.model_dump()
    data["packages"] = sorted({round(p, 2) for p in body.packages if p > 0})
    data.update({"updated_at": now_iso(), "updated_by": admin["email"]})
    await db.settings.update_one({"key": "platform"}, {"$set": data}, upsert=True)
    return await get_settings()


@api.get("/admin/fraud")
async def admin_fraud(status: Optional[str] = None, _: dict = Depends(require_admin)):
    q = {"status": status} if status and status != "all" else {}
    return await db.fraud_alerts.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/admin/fraud/{alert_id}/resolve")
async def admin_resolve_alert(alert_id: str, admin: dict = Depends(require_admin)):
    res = await db.fraud_alerts.update_one({"id": alert_id}, {"$set": {"status": "resolved", "resolved_by": admin["email"],
                                                                       "resolved_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True}


@api.get("/admin/tickets")
async def admin_tickets(_: dict = Depends(require_admin)):
    return await db.tickets.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)


@api.post("/admin/tickets/{ticket_id}/reply")
async def admin_reply(ticket_id: str, body: ReplyIn, admin: dict = Depends(require_admin)):
    return await append_reply(ticket_id, admin, body.message, {})


@api.patch("/admin/tickets/{ticket_id}/status")
async def admin_ticket_status(ticket_id: str, body: TicketStatusIn, _: dict = Depends(require_admin)):
    t = await db.tickets.find_one_and_update({"id": ticket_id}, {"$set": {"status": body.status, "updated_at": now_iso()}},
                                             projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t


# ---------- Seed ----------
async def seed() -> None:
    if not await db.settings.find_one({"key": "platform"}):
        await db.settings.insert_one({"key": "platform", **DEFAULT_SETTINGS})
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    if not await db.users.find_one({"email": admin_email}):
        await db.users.insert_one({"id": new_id(), "email": admin_email, "name": "Platform Admin",
                                   "password_hash": hash_password(os.environ["ADMIN_PASSWORD"]), "role": "admin",
                                   "status": "active", "email_verified": True, "real_balance": 0.0,
                                   "promo_balance": 0.0, "created_at": now_iso()})
    demo_email = os.environ["DEMO_EMAIL"].lower()
    if not await db.users.find_one({"email": demo_email}):
        demo = {"id": new_id(), "email": demo_email, "name": "Demo Player", "country": "India",
                "password_hash": hash_password(os.environ["DEMO_PASSWORD"]), "role": "user", "status": "active",
                "email_verified": True, "real_balance": 0.0, "promo_balance": 0.0, "created_at": now_iso()}
        await db.users.insert_one(demo)
        s = await get_settings()
        for amount, status in ((20000.0, "approved"), (50000.0, "pending")):
            dep = {"id": new_id(), "reference": f"DEP-{secrets.token_hex(4).upper()}", "user_id": demo["id"],
                   "user_email": demo_email, "user_name": demo["name"], "amount": amount, "currency": "INR",
                   "method": "upi", **compute_breakdown(amount, s), "status": status, "fraud_flags": [],
                   "risk_score": 12, "created_at": now_iso()}
            if status == "approved":
                dep.update({"reviewed_at": now_iso(), "reviewed_by": admin_email})
            await db.deposits.insert_one(dict(dep))
            if status == "approved":
                await credit_deposit(dep)


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=[FRONTEND_URL],
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    app.state.index_task = asyncio.create_task(ensure_indexes())
    await seed()


@app.on_event("shutdown")
async def shutdown():
    app.state.index_task.cancel()
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    client.close()
