# Account settings (PUT /api/auth/account) + Scarmenta branding API checks
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
mdb = MongoClient("mongodb://localhost:27017")["test_database"]
PWD = "TestPass@123"


def new_user():
    s = requests.Session()
    email = f"test_acct_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={"name": "TEST_Acct", "email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return s, r.json()


@pytest.fixture(scope="module")
def created():
    ids = []
    yield ids
    for uid in ids:
        mdb.users.delete_one({"id": uid, "email": {"$regex": "^test_(acct|new)_"}})
        mdb.login_attempts.delete_many({"identifier": f"account:{uid}"})
        mdb.email_tokens.delete_many({"user_id": uid})


# Registration / referral prefix
def test_referral_code_starts_with_sc(created):
    s, u = new_user()
    created.append(u["id"])
    assert u["referral_code"].startswith("SC")


# Auth required
def test_account_requires_auth():
    r = requests.put(f"{BASE_URL}/api/auth/account", json={"current_password": "x", "name": "TEST_x"})
    assert r.status_code == 401


def test_wrong_password_401(created):
    s, u = new_user(); created.append(u["id"])
    r = s.put(f"{BASE_URL}/api/auth/account", json={"current_password": "wrong-pass", "name": "TEST_New"})
    assert r.status_code == 401
    assert "incorrect" in r.json()["detail"].lower()


def test_lockout_after_5_wrong(created):
    s, u = new_user(); created.append(u["id"])
    codes = [s.put(f"{BASE_URL}/api/auth/account", json={"current_password": "wrong-pass", "name": "TEST_N"}).status_code
             for _ in range(6)]
    print("codes:", codes)
    # lock must be effective: correct password now rejected with 429
    r = s.put(f"{BASE_URL}/api/auth/account", json={"current_password": PWD, "name": "TEST_Locked"})
    assert r.status_code == 429
    assert codes[5] == 429


def test_fifth_wrong_returns_429(created):
    s, u = new_user(); created.append(u["id"])
    codes = [s.put(f"{BASE_URL}/api/auth/account", json={"current_password": "wrong-pass", "name": "TEST_N"}).status_code
             for _ in range(5)]
    assert codes[4] == 429, f"5th wrong attempt returned {codes[4]} (codes={codes})"


def test_change_name_only(created):
    s, u = new_user(); created.append(u["id"])
    r = s.put(f"{BASE_URL}/api/auth/account", json={"current_password": PWD, "name": "TEST_Renamed"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "TEST_Renamed"
    assert "password_hash" not in r.json() and "_id" not in r.json()
    me = s.get(f"{BASE_URL}/api/auth/me").json()
    assert me["name"] == "TEST_Renamed"


def test_duplicate_email_400(created):
    s, u = new_user(); created.append(u["id"])
    r = s.put(f"{BASE_URL}/api/auth/account", json={"current_password": PWD, "email": "demo@aetheria.io"})
    assert r.status_code == 400


def test_nothing_changed_400(created):
    s, u = new_user(); created.append(u["id"])
    r = s.put(f"{BASE_URL}/api/auth/account", json={"current_password": PWD, "name": u["name"], "email": u["email"]})
    assert r.status_code == 400
    assert "nothing" in r.json()["detail"].lower()


def test_short_new_password_422(created):
    s, u = new_user(); created.append(u["id"])
    r = s.put(f"{BASE_URL}/api/auth/account", json={"current_password": PWD, "new_password": "short"})
    assert r.status_code == 422


def test_player_email_change_unverifies_and_password_change(created):
    s, u = new_user(); created.append(u["id"])
    mdb.users.update_one({"id": u["id"]}, {"$set": {"email_verified": True}})
    new_email = f"test_new_{uuid.uuid4().hex[:8]}@example.com"
    r = s.put(f"{BASE_URL}/api/auth/account",
              json={"current_password": PWD, "email": new_email.upper(), "new_password": "NewPass@999"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["email"] == new_email and d["email_verified"] is False
    assert mdb.email_tokens.find_one({"user_id": u["id"], "kind": "verify", "used": False})
    # old creds fail, new creds work
    assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": u["email"], "password": PWD}).status_code == 401
    assert requests.post(f"{BASE_URL}/api/auth/login", json={"email": new_email, "password": PWD}).status_code == 401
    r2 = requests.post(f"{BASE_URL}/api/auth/login", json={"email": new_email, "password": "NewPass@999"})
    assert r2.status_code == 200


def test_whitespace_name_rejected(created):
    s, u = new_user(); created.append(u["id"])
    r = s.put(f"{BASE_URL}/api/auth/account", json={"current_password": PWD, "name": "   "})
    print(r.status_code, r.text)
    assert r.status_code in (400, 422), f"whitespace name accepted -> {r.json()}"


# Regression: password login works for seeded accounts
@pytest.mark.parametrize("email,pwd,role", [("admin@aetheria.io", "Admin@12345", "admin"),
                                             ("demo@aetheria.io", "Demo@12345", "user")])
def test_seed_login(email, pwd, role):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == role
    assert "access_token" in r.cookies or "httponly" in r.headers.get("set-cookie", "").lower()


def test_bcrypt_hash_format():
    for u in mdb.users.find({"email": {"$in": ["admin@aetheria.io", "demo@aetheria.io"]}}):
        assert u["password_hash"].startswith("$2b$")
