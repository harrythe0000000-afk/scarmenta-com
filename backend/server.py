from core import (db, client, new_ticket, now, now_iso, new_id, clean, hash_password, verify_password, set_auth_cookies,
                  set_access_cookie, clear_auth_cookies, decode_token, get_current_user, require_admin, require_staff,
                  get_settings, compute_breakdown, client_ip, DEFAULT_SETTINGS, SITE_ORIGINS, site_url, make_tx,
                  unique_referral_code)
from emailer import send_verification_email, send_reset_email, send_otp_email, send_deposit_alert
import games
import referrals
import rewards
import agents
import content
import assistant

import asyncio
import logging
import os
import re
import secrets
from contextlib import suppress
from datetime import timedelta, timezone
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument
from pymongo.errors import DuplicateKeyError
from starlette.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

INDEXES: dict[str, list[IndexModel]] = {
    "users": [IndexModel([("email", ASCENDING)], name="email", unique=True),
              IndexModel([("id", ASCENDING)], name="id", unique=True),
              IndexModel([("referral_code", ASCENDING)], name="referral_code", unique=True, sparse=True),
              IndexModel([("referred_by", ASCENDING)], name="referred_by"),
              IndexModel([("agent_code", ASCENDING)], name="agent_code", unique=True, sparse=True),
              IndexModel([("agent_id", ASCENDING)], name="agent_id")],
    "deposits": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                 IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created"),
                 IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created")],
    "transactions": [IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created"),
                     IndexModel([("created_at", DESCENDING)], name="created_desc")],
    "tickets": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                IndexModel([("user_id", ASCENDING), ("updated_at", DESCENDING)], name="user_updated")],
    "fraud_alerts": [IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created")],
    "transfers": [IndexModel([("from_user_id", ASCENDING), ("created_at", DESCENDING)], name="from_created"),
                  IndexModel([("to_user_id", ASCENDING), ("created_at", DESCENDING)], name="to_created")],
    "agent_commissions": [IndexModel([("agent_id", ASCENDING), ("created_at", DESCENDING)], name="agent_created")],
    "providers": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                  IndexModel([("code", ASCENDING)], name="code", unique=True),
                  IndexModel([("api_key_hash", ASCENDING)], name="api_key_hash")],
    "game_sessions": [IndexModel([("token", ASCENDING)], name="token", unique=True),
                      IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=86400)],
    "game_transactions": [IndexModel([("provider_id", ASCENDING), ("external_tx_id", ASCENDING)], name="provider_ext", unique=True),
                          IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created"),
                          IndexModel([("provider_id", ASCENDING), ("round_id", ASCENDING), ("user_id", ASCENDING)], name="round"),
                          IndexModel([("created_at", DESCENDING)], name="created_desc")],
    "loss_reward_runs": [IndexModel([("period_end", DESCENDING)], name="period_end")],
    "login_otps": [IndexModel([("email", ASCENDING)], name="email"),
                   IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=0)],
    "login_attempts": [IndexModel([("identifier", ASCENDING)], name="identifier")],
    "email_tokens": [IndexModel([("token", ASCENDING)], name="token", unique=True),
                     IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=0)],
    "chat_messages": [IndexModel([("user_id", ASCENDING), ("session_id", ASCENDING), ("created_at", ASCENDING)], name="user_session")],
    "banner_events": [IndexModel([("banner_id", ASCENDING), ("user_id", ASCENDING), ("type", ASCENDING)],
                                 name="banner_user_type", unique=True)],
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

NETWORKS = {"TRC20": "usdt_trc20", "ERC20": "usdt_erc20", "BEP20": "usdt_bep20"}


# ---------- Models ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    country: Optional[str] = Field(default=None, max_length=60)
    referral_code: Optional[str] = Field(default=None, max_length=20)
    agent_code: Optional[str] = Field(default=None, max_length=20)
    accepted_terms: bool = False
    terms_version: Optional[str] = Field(default=None, max_length=20)
    signup_source: Optional[Literal["calc_share"]] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class OtpVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class AccountIn(BaseModel):
    current_password: str
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    email: Optional[EmailStr] = None
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class StaffIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TransferIn(BaseModel):
    to_email: EmailStr
    to_password: str
    amount: float = Field(gt=0)


class TokenIn(BaseModel):
    token: str


class EmailIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class DepositIn(BaseModel):
    amount: float = Field(gt=0)
    method: Literal["usdt", "upi"]
    network: Optional[Literal["TRC20", "ERC20", "BEP20"]] = None
    payment_reference: str = Field(min_length=6, max_length=120)


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
    referral_bonus_percent: float = Field(ge=0, le=100)
    loss_reward_percent: float = Field(ge=0, le=100)
    deposit_alerts: bool
    transfer_fee_percent: float = Field(ge=0, le=50)
    share_bonus_amount: Optional[float] = Field(default=None, ge=0, le=1000)
    packages: List[float] = Field(min_length=1, max_length=8)
    fx_rates: Dict[str, float]
    upi_id: str = Field(max_length=100)
    usdt_trc20: str = Field(max_length=120)
    usdt_erc20: str = Field(max_length=120)
    usdt_bep20: str = Field(max_length=120)


# ---------- Helpers ----------
async def credit_deposit(dep: dict) -> None:
    user = await db.users.find_one_and_update(
        {"id": dep["user_id"]},
        {"$inc": {"promo_balance": dep["promo_credit"]}},
        projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    via = f"USDT {dep.get('network') or ''}".strip() if dep["method"] == "usdt" else "UPI"
    desc = f"${dep['amount']:,.2f} deposit via {via} · {dep['promo_multiplier']:g}X credit allocation"
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


async def send_verification(user: dict, base_url: str) -> bool:
    token = await issue_token(user, "verify", 24)
    try:
        await send_verification_email(user, token, base_url)
        return True
    except Exception as exc:
        logger.error("verification email failed for %s: %s", user["email"], exc)
        return False


# ---------- Auth ----------
@api.post("/auth/register")
async def register(body: RegisterIn, request: Request, response: Response):
    if not body.accepted_terms:
        raise HTTPException(status_code=400, detail="You must accept the Terms & Conditions to register")
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    referrer = None
    if body.referral_code and body.referral_code.strip():
        referrer = await db.users.find_one({"referral_code": body.referral_code.strip().upper(), "role": "user"},
                                           {"_id": 0, "id": 1, "email": 1})
        if not referrer:
            raise HTTPException(status_code=400, detail="Invalid referral code")
    agent = None
    if body.agent_code and body.agent_code.strip():
        agent = await db.users.find_one({"agent_code": body.agent_code.strip().upper(), "role": "agent", "status": "active"},
                                        {"_id": 0, "id": 1})
        if not agent:
            raise HTTPException(status_code=400, detail="Invalid agent code")
    user = {"id": new_id(), "email": email, "name": body.name.strip(), "country": body.country,
            "password_hash": hash_password(body.password), "role": "user", "status": "active",
            "email_verified": False, "promo_balance": 0.0, "referral_code": await unique_referral_code(),
            "referred_by": referrer["id"] if referrer else None,
            "referred_by_email": referrer["email"] if referrer else None,
            "signup_source": body.signup_source if referrer else None,
            "agent_id": agent["id"] if agent else None, "created_at": now_iso(),
            "terms_accepted_at": now_iso(), "terms_version": body.terms_version}
    await db.users.insert_one(user)
    sent = await send_verification(user, site_url(request))
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


@api.post("/auth/otp/request")
async def otp_request(body: EmailIn):
    email = body.email.lower()
    user = await db.users.find_one({"email": email, "status": "active"}, {"_id": 0, "password_hash": 0})
    if not user:
        return {"ok": True}
    since = (now() - timedelta(seconds=60)).isoformat()
    if await db.login_otps.find_one({"email": email, "created_at": {"$gte": since}}):
        raise HTTPException(status_code=429, detail="Please wait a minute before requesting another code")
    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.login_otps.delete_many({"email": email})
    await db.login_otps.insert_one({"email": email, "code_hash": hash_password(code), "attempts": 0,
                                    "created_at": now_iso(), "expires_at": now() + timedelta(minutes=10)})
    try:
        await send_otp_email(user, code)
    except Exception as exc:
        logger.error("otp email failed for %s: %s", email, exc)
        await db.login_otps.delete_many({"email": email})
        raise HTTPException(status_code=503, detail="Could not send the code right now. Try again shortly.")
    return {"ok": True}


@api.post("/auth/otp/verify")
async def otp_verify(body: OtpVerifyIn, request: Request, response: Response):
    email = body.email.lower()
    otp = await db.login_otps.find_one({"email": email})
    if not otp or otp["expires_at"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(status_code=400, detail="This code has expired. Request a new one.")
    if otp["attempts"] >= 5:
        await db.login_otps.delete_many({"email": email})
        raise HTTPException(status_code=429, detail="Too many wrong codes. Request a new one.")
    if not verify_password(body.code, otp["code_hash"]):
        await db.login_otps.update_one({"_id": otp["_id"]}, {"$inc": {"attempts": 1}})
        raise HTTPException(status_code=401, detail="Incorrect code")
    await db.login_otps.delete_many({"email": email})
    existing = await db.users.find_one({"email": email}, {"_id": 0, "status": 1})
    if not existing:
        raise HTTPException(status_code=400, detail="This code has expired. Request a new one.")
    if existing.get("status") == "suspended":
        raise HTTPException(status_code=403, detail="Account suspended. Contact support.")
    user = await db.users.find_one_and_update(
        {"email": email}, {"$set": {"email_verified": True, "last_login_at": now_iso(), "last_ip": client_ip(request)}},
        projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    set_auth_cookies(response, user)
    return user


@api.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.put("/auth/account")
async def update_account(body: AccountIn, request: Request, response: Response, user: dict = Depends(get_current_user)):
    ident = f"account:{user['id']}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("locked_until") and att["locked_until"] > now_iso():
        raise HTTPException(status_code=429, detail="Too many wrong passwords. Try again in 15 minutes.")
    full = await db.users.find_one({"id": user["id"]})
    if not verify_password(body.current_password, full["password_hash"]):
        count = (att or {}).get("count", 0) + 1
        update = {"count": 0, "locked_until": (now() + timedelta(minutes=15)).isoformat()} if count >= 5 else {"count": count}
        await db.login_attempts.update_one({"identifier": ident}, {"$set": update}, upsert=True)
        if count >= 5:
            raise HTTPException(status_code=429, detail="Too many wrong passwords. Try again in 15 minutes.")
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    await db.login_attempts.delete_one({"identifier": ident})
    changes: dict = {}
    if body.name is not None and not body.name.strip():
        raise HTTPException(status_code=422, detail="Name cannot be blank")
    if body.name and body.name.strip() != full["name"]:
        changes["name"] = body.name.strip()
    new_email = body.email.lower() if body.email else None
    if new_email and new_email != full["email"]:
        if await db.users.find_one({"email": new_email}):
            raise HTTPException(status_code=400, detail="An account with this email already exists")
        changes["email"] = new_email
        if full["role"] == "user":
            changes["email_verified"] = False
    if body.new_password:
        changes["password_hash"] = hash_password(body.new_password)
    if not changes:
        raise HTTPException(status_code=400, detail="Nothing to update")
    changes["updated_at"] = now_iso()
    updated = await db.users.find_one_and_update({"id": user["id"]}, {"$set": changes},
                                                 projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    if "email" in changes and full["role"] == "user":
        await send_verification(updated, site_url(request))
    set_auth_cookies(response, updated)
    return updated


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
async def resend_verification(request: Request, user: dict = Depends(get_current_user)):
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email already verified")
    since = (now() - timedelta(seconds=60)).isoformat()
    if await db.email_tokens.find_one({"user_id": user["id"], "kind": "verify", "created_at": {"$gte": since}}):
        raise HTTPException(status_code=429, detail="Please wait a minute before requesting another email")
    if not await send_verification(user, site_url(request)):
        raise HTTPException(status_code=503, detail="Could not send email right now. Try again shortly.")
    return {"ok": True}


@api.post("/auth/forgot-password")
async def forgot_password(body: EmailIn, request: Request):
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0, "password_hash": 0})
    if user:
        token = await issue_token(user, "reset", 1)
        try:
            await send_reset_email(user, token, site_url(request))
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
    out = {k: s[k] for k in ("promo_multiplier", "min_deposit", "max_deposit", "packages", "fx_rates",
                             "referral_bonus_percent", "loss_reward_percent", "transfer_fee_percent",
                             "share_bonus_amount")}
    out["currency"] = "USD"
    out["payment"] = {"upi_id": s["upi_id"], "usdt": {n: s[k] for n, k in NETWORKS.items()}}
    return out


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
            "total_credits": totals["credits"], "approved_count": totals["count"], "pending_count": pending,
            "referral_earnings": user.get("referral_earnings", 0), "loss_rewards": user.get("loss_rewards_total", 0)}


BG_TASKS: set = set()


async def notify_staff(dep: dict, base_url: str) -> None:
    team = await db.users.find({"role": {"$in": ["admin", "staff"]}, "status": "active"}, {"_id": 0, "name": 1, "email": 1}).to_list(100)
    for m in team:
        try:
            await send_deposit_alert(m["name"], m["email"], dep, base_url)
        except Exception as exc:
            logger.error("deposit alert to %s failed: %s", m["email"], exc)


@api.post("/deposits")
async def create_deposit(body: DepositIn, request: Request, user: dict = Depends(get_current_user)):
    if user.get("role") != "user":
        raise HTTPException(status_code=403, detail="Only player accounts can deposit")
    if not user.get("email_verified"):
        raise HTTPException(status_code=403, detail="Please verify your email before making a deposit")
    s = await get_settings()
    if body.amount < s["min_deposit"] or body.amount > s["max_deposit"]:
        raise HTTPException(status_code=400, detail=f"Deposit must be between ${s['min_deposit']:,.0f} and ${s['max_deposit']:,.0f}")
    if body.method == "usdt":
        if not body.network:
            raise HTTPException(status_code=400, detail="Choose a USDT network")
        if not s[NETWORKS[body.network]]:
            raise HTTPException(status_code=400, detail=f"USDT {body.network} deposits are not available yet")
        local = {"network": body.network, "pay_to": s[NETWORKS[body.network]], "local_currency": "USDT",
                 "fx_rate": 1.0, "local_amount": round(body.amount, 2)}
    else:
        rate = s["fx_rates"].get("INR")
        if not s["upi_id"] or not rate:
            raise HTTPException(status_code=400, detail="UPI deposits are not available yet")
        local = {"network": None, "pay_to": s["upi_id"], "local_currency": "INR", "fx_rate": rate,
                 "local_amount": round(body.amount * rate, 2)}
    ref = body.payment_reference.strip()
    try:
        await db.payment_refs.insert_one({"_id": ref.upper(), "user_id": user["id"], "created_at": now_iso()})
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="This payment reference has already been submitted")
    since = (now() - timedelta(hours=24)).isoformat()
    recent = await db.deposits.count_documents({"user_id": user["id"], "created_at": {"$gte": since}})
    flags = []
    if body.amount >= s["fraud_amount_threshold"]:
        flags.append("high_amount")
    if recent + 1 >= s["fraud_velocity_count"]:
        flags.append("velocity")
    dep = {"id": new_id(), "reference": f"DEP-{secrets.token_hex(4).upper()}", "user_id": user["id"],
           "user_email": user["email"], "user_name": user["name"], "amount": round(body.amount, 2), "currency": "USD",
           "method": body.method, **local, "payment_reference": ref, **compute_breakdown(body.amount, s),
           "status": "pending", "fraud_flags": flags,
           "risk_score": min(100, 12 + 38 * len(flags)), "created_at": now_iso()}
    await db.deposits.insert_one(dep)
    if "high_amount" in flags:
        await add_alert("high_amount", "high", f"Deposit {dep['reference']} of ${body.amount:,.2f} exceeds threshold", user, dep["reference"])
    if "velocity" in flags:
        await add_alert("velocity", "medium", f"{recent + 1} deposits in 24h by {user['email']}", user, dep["reference"])
    if s.get("deposit_alerts", True):
        task = asyncio.create_task(notify_staff(dict(dep), site_url(request)))
        BG_TASKS.add(task)
        task.add_done_callback(BG_TASKS.discard)
    return clean(dep)


@api.post("/transfers")
async def create_transfer(body: TransferIn, user: dict = Depends(get_current_user)):
    if user.get("role") != "user":
        raise HTTPException(status_code=403, detail="Only player accounts can transfer")
    ident = f"transfer:{user['id']}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("locked_until") and att["locked_until"] > now_iso():
        raise HTTPException(status_code=429, detail="Too many wrong passwords. Try again in 15 minutes.")
    to = await db.users.find_one({"email": body.to_email.lower(), "role": "user"})
    if not to or to["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Enter the email of your other player account")
    if not verify_password(body.to_password, to["password_hash"]):
        count = (att or {}).get("count", 0) + 1
        update = {"count": 0, "locked_until": (now() + timedelta(minutes=15)).isoformat()} if count >= 5 else {"count": count}
        await db.login_attempts.update_one({"identifier": ident}, {"$set": update}, upsert=True)
        raise HTTPException(status_code=429 if count >= 5 else 401, detail="The password for the receiving account is incorrect")
    await db.login_attempts.delete_one({"identifier": ident})
    if to.get("status") != "active":
        raise HTTPException(status_code=400, detail="The receiving account is not active")
    s = await get_settings()
    amount = round(body.amount, 2)
    fee = round(amount * s["transfer_fee_percent"] / 100, 2)
    net = round(amount - fee, 2)
    src = await db.users.find_one_and_update({"id": user["id"], "promo_balance": {"$gte": amount}},
                                             {"$inc": {"promo_balance": -amount}},
                                             projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    if not src:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    dst = await db.users.find_one_and_update({"id": to["id"]}, {"$inc": {"promo_balance": net}},
                                             projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    ref = f"TRF-{secrets.token_hex(4).upper()}"
    rec = {"id": new_id(), "reference": ref, "from_user_id": user["id"], "from_email": user["email"], "to_user_id": to["id"],
           "to_email": to["email"], "amount": amount, "fee_percent": s["transfer_fee_percent"], "fee": fee, "net": net,
           "created_at": now_iso()}
    await db.transfers.insert_one(dict(rec))
    await db.transactions.insert_many([
        make_tx(src, "transfer_out", "credit", -amount, f"Transfer to {to['email']} (incl. {s['transfer_fee_percent']:g}% fee ${fee:,.2f})", ref, src["promo_balance"]),
        make_tx(dst, "transfer_in", "credit", net, f"Transfer from {user['email']}", ref, dst["promo_balance"])])
    return rec


@api.get("/transfers")
async def my_transfers(user: dict = Depends(get_current_user)):
    return await db.transfers.find({"$or": [{"from_user_id": user["id"]}, {"to_user_id": user["id"]}]}, {"_id": 0}
                                   ).sort("created_at", -1).to_list(500)


@api.get("/admin/transfers")
async def admin_transfers(_: dict = Depends(require_staff)):
    return await db.transfers.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


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
    t = new_ticket(user, body.subject, body.category, body.message)
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
async def admin_stats(_: dict = Depends(require_staff)):
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
async def admin_users(q: Optional[str] = None, _: dict = Depends(require_staff)):
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
async def admin_deposits(status: Optional[str] = None, _: dict = Depends(require_staff)):
    q = {"status": status} if status and status != "all" else {}
    return await db.deposits.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.post("/admin/deposits/{dep_id}/approve")
async def admin_approve(dep_id: str, admin: dict = Depends(require_staff)):
    dep = await db.deposits.find_one_and_update(
        {"id": dep_id, "status": "pending"},
        {"$set": {"status": "approved", "reviewed_at": now_iso(), "reviewed_by": admin["email"]}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not dep:
        raise HTTPException(status_code=409, detail="Deposit not found or already reviewed")
    await credit_deposit(dep)
    await referrals.reward_referrer(dep)
    await referrals.reward_share(dep)
    await agents.reward_agent(dep)
    return dep


@api.post("/admin/deposits/{dep_id}/reject")
async def admin_reject(dep_id: str, body: RejectIn, admin: dict = Depends(require_staff)):
    dep = await db.deposits.find_one_and_update(
        {"id": dep_id, "status": "pending"},
        {"$set": {"status": "rejected", "reviewed_at": now_iso(), "reviewed_by": admin["email"],
                  "reject_reason": body.reason}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not dep:
        raise HTTPException(status_code=409, detail="Deposit not found or already reviewed")
    if dep.get("payment_reference"):
        await db.payment_refs.delete_one({"_id": dep["payment_reference"].upper()})
    return dep


@api.get("/admin/transactions")
async def admin_transactions(q: Optional[str] = None, type: Optional[str] = None, wallet: Optional[str] = None,
                             start: Optional[str] = None, end: Optional[str] = None, _: dict = Depends(require_staff)):
    query = tx_query({}, type, wallet, start, end)
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"user_email": rx}, {"reference": rx}, {"description": rx}]
    return await db.transactions.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.get("/admin/staff")
async def list_staff(_: dict = Depends(require_admin)):
    return await db.users.find({"role": {"$in": ["admin", "staff"]}}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(200)


@api.post("/admin/staff")
async def create_staff(body: StaffIn, admin: dict = Depends(require_admin)):
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Name cannot be blank")
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    staff = {"id": new_id(), "email": email, "name": body.name.strip(), "password_hash": hash_password(body.password),
             "role": "staff", "status": "active", "email_verified": True, "promo_balance": 0.0,
             "created_by": admin["email"], "created_at": now_iso()}
    await db.users.insert_one(staff)
    return clean(staff)


@api.patch("/admin/staff/{staff_id}/status")
async def staff_status(staff_id: str, body: UserStatusIn, _: dict = Depends(require_admin)):
    res = await db.users.update_one({"id": staff_id, "role": "staff"}, {"$set": {"status": body.status}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {"ok": True}


@api.get("/admin/settings")
async def admin_get_settings(_: dict = Depends(require_admin)):
    return await get_settings()


@api.put("/admin/settings")
async def admin_put_settings(body: SettingsIn, admin: dict = Depends(require_admin)):
    if body.min_deposit >= body.max_deposit:
        raise HTTPException(status_code=400, detail="Minimum deposit must be lower than maximum")
    if any(p < body.min_deposit or p > body.max_deposit for p in body.packages):
        raise HTTPException(status_code=400, detail="Every package must be within the min/max deposit limits")
    rates = {}
    for code, rate in body.fx_rates.items():
        c = code.strip().upper()
        if not re.fullmatch(r"[A-Z]{3,5}", c) or rate <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid currency rate: {code}")
        rates[c] = round(rate, 6)
    data = body.model_dump(exclude_none=True)
    data["fx_rates"] = rates
    data.update({k: data[k].strip() for k in ("upi_id", "usdt_trc20", "usdt_erc20", "usdt_bep20")})
    data["packages"] = sorted({round(p, 2) for p in body.packages if p > 0})
    data.update({"updated_at": now_iso(), "updated_by": admin["email"]})
    await db.settings.update_one({"key": "platform"}, {"$set": data}, upsert=True)
    return await get_settings()


@api.get("/admin/fraud")
async def admin_fraud(status: Optional[str] = None, _: dict = Depends(require_staff)):
    q = {"status": status} if status and status != "all" else {}
    return await db.fraud_alerts.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/admin/fraud/{alert_id}/resolve")
async def admin_resolve_alert(alert_id: str, admin: dict = Depends(require_staff)):
    res = await db.fraud_alerts.update_one({"id": alert_id}, {"$set": {"status": "resolved", "resolved_by": admin["email"],
                                                                       "resolved_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True}


@api.get("/admin/tickets")
async def admin_tickets(_: dict = Depends(require_staff)):
    return await db.tickets.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)


@api.post("/admin/tickets/{ticket_id}/reply")
async def admin_reply(ticket_id: str, body: ReplyIn, admin: dict = Depends(require_staff)):
    return await append_reply(ticket_id, admin, body.message, {})


@api.patch("/admin/tickets/{ticket_id}/status")
async def admin_ticket_status(ticket_id: str, body: TicketStatusIn, _: dict = Depends(require_staff)):
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
    if not await db.users.find_one({"role": "admin"}):
        await db.users.insert_one({"id": new_id(), "email": admin_email, "name": "Platform Admin",
                                   "password_hash": hash_password(os.environ["ADMIN_PASSWORD"]), "role": "admin",
                                   "status": "active", "email_verified": True,
                                   "promo_balance": 0.0, "created_at": now_iso()})
    await games.seed_providers()
    demo_email = os.environ["DEMO_EMAIL"].lower()
    if not await db.users.find_one({"email": demo_email}):
        demo = {"id": new_id(), "email": demo_email, "name": "Demo Player", "country": "India",
                "password_hash": hash_password(os.environ["DEMO_PASSWORD"]), "role": "user", "status": "active",
                "email_verified": True, "promo_balance": 0.0, "referral_code": await unique_referral_code(),
                "created_at": now_iso()}
        await db.users.insert_one(demo)
        s = await get_settings()
        for amount, status in ((200.0, "approved"), (500.0, "pending")):
            dep = {"id": new_id(), "reference": f"DEP-{secrets.token_hex(4).upper()}", "user_id": demo["id"],
                   "user_email": demo_email, "user_name": demo["name"], "amount": amount, "currency": "USD",
                   "method": "usdt", "network": "TRC20", "pay_to": "demo-seed", "local_currency": "USDT",
                   "fx_rate": 1.0, "local_amount": amount, "payment_reference": f"DEMO-SEED-{secrets.token_hex(4)}",
                   **compute_breakdown(amount, s), "status": status, "fraud_flags": [],
                   "risk_score": 12, "created_at": now_iso()}
            if status == "approved":
                dep.update({"reviewed_at": now_iso(), "reviewed_by": admin_email})
            await db.deposits.insert_one(dict(dep))
            if status == "approved":
                await credit_deposit(dep)


app.include_router(api)
app.include_router(referrals.router)
app.include_router(games.router)
app.include_router(rewards.router)
app.include_router(agents.router)
app.include_router(content.router)
app.include_router(assistant.router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=sorted(SITE_ORIGINS),
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    app.state.index_task = asyncio.create_task(ensure_indexes())
    await seed()
    try:
        await asyncio.to_thread(content.init_storage)
    except Exception as e:
        logging.getLogger(__name__).error(f"Storage init failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    app.state.index_task.cancel()
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    client.close()
