from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
FRONTEND_URL = os.environ["FRONTEND_URL"]
JWT_ALGORITHM = "HS256"

DEFAULT_SETTINGS = {
    "promo_multiplier": 5.0,
    "min_deposit": 1000.0,
    "max_deposit": 500000.0,
    "fraud_amount_threshold": 100000.0,
    "fraud_velocity_count": 3,
    "referral_bonus_percent": 10.0,
    "packages": [5000.0, 10000.0, 20000.0, 50000.0, 100000.0],
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def clean(doc: dict) -> dict:
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": now() + timedelta(minutes=15), "type": "access"}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": now() + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload


def set_access_cookie(response: Response, user: dict) -> None:
    response.set_cookie("access_token", create_access_token(user["id"], user["email"]), httponly=True,
                        secure=True, samesite="none", max_age=900, path="/")


def set_auth_cookies(response: Response, user: dict) -> None:
    set_access_cookie(response, user)
    response.set_cookie("refresh_token", create_refresh_token(user["id"]), httponly=True,
                        secure=True, samesite="none", max_age=604800, path="/")


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/", secure=True, samesite="none")
    response.delete_cookie("refresh_token", path="/", secure=True, samesite="none")


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token, "access")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.get("status") == "suspended":
        raise HTTPException(status_code=403, detail="Account suspended. Contact support.")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_settings() -> dict:
    doc = await db.settings.find_one({"key": "platform"}, {"_id": 0, "key": 0}) or {}
    return {**DEFAULT_SETTINGS, **doc}


def compute_breakdown(amount: float, s: dict) -> dict:
    return {"promo_multiplier": s["promo_multiplier"], "promo_credit": round(amount * s["promo_multiplier"], 2)}


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def make_tx(user: dict, kind: str, wallet: str, amount: float, description: str, reference: str, balance_after: float) -> dict:
    return {"id": new_id(), "user_id": user["id"], "user_email": user["email"], "user_name": user.get("name", ""),
            "type": kind, "wallet": wallet, "amount": round(amount, 2), "description": description,
            "reference": reference, "balance_after": round(balance_after, 2), "created_at": now_iso()}


async def unique_referral_code() -> str:
    import secrets
    while True:
        code = "AE" + secrets.token_hex(3).upper()
        if not await db.users.find_one({"referral_code": code}):
            return code
