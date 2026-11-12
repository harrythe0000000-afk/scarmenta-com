# SquareManta - email OTP login + rebrand (SM referral codes) + password login regression
import os
import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
ADMIN = ("admin@aetheria.io", "Admin@12345")
DEMO = ("demo@aetheria.io", "Demo@12345")
mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
CREATED = []


def make_user():
    s = requests.Session()
    email = f"test_otp_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"name": "TEST Otp", "email": email, "password": "Test@12345"})
    assert r.status_code == 200, r.text
    CREATED.append(r.json()["id"])
    return r.json()


def set_code(email, code="123456", minutes=10, attempts=0):
    mongo.login_otps.delete_many({"email": email})
    mongo.login_otps.insert_one({"email": email, "code_hash": bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode(),
                                 "attempts": attempts, "created_at": datetime.now(timezone.utc).isoformat(),
                                 "expires_at": datetime.now(timezone.utc) + timedelta(minutes=minutes)})


def verify(email, code, s=None):
    return (s or requests).post(f"{API}/auth/otp/verify", json={"email": email, "code": code})


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in CREATED:
        u = mongo.users.find_one({"id": uid})
        if u:
            mongo.login_otps.delete_many({"email": u["email"]})
        for c in ("email_tokens", "transactions", "deposits"):
            mongo[c].delete_many({"user_id": uid})
        mongo.users.delete_one({"id": uid})


class TestPasswordLoginRegression:
    @pytest.mark.parametrize("creds,role", [(ADMIN, "admin"), (DEMO, "user")])
    def test_password_login(self, creds, role):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": creds[0], "password": creds[1]})
        assert r.status_code == 200, r.text
        assert r.json()["role"] == role
        assert "access_token" in s.cookies
        assert s.get(f"{API}/auth/me").json()["email"] == creds[0]


class TestOtp:
    def test_new_referral_code_sm(self):
        u = make_user()
        assert u["referral_code"].startswith("SC")
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": u["email"], "password": "Test@12345"})
        r = s.get(f"{API}/referrals/me")
        assert r.status_code == 200
        assert str(r.json().get("referral_code", r.json().get("code", ""))).startswith("SC"), r.json()

    def test_unknown_email_ok(self):
        r = requests.post(f"{API}/auth/otp/request", json={"email": f"nobody_{uuid.uuid4().hex[:6]}@example.com"})
        assert r.status_code == 200 and r.json() == {"ok": True}

    def test_demo_request_then_429(self):
        mongo.login_otps.delete_many({"email": DEMO[0]})
        r = requests.post(f"{API}/auth/otp/request", json={"email": DEMO[0]})
        assert r.status_code in (200, 502), r.text
        if r.status_code == 502:
            pytest.skip("email provider failed (502)")
        assert r.json() == {"ok": True}
        r2 = requests.post(f"{API}/auth/otp/request", json={"email": DEMO[0]})
        assert r2.status_code == 429
        mongo.login_otps.delete_many({"email": DEMO[0]})

    def test_wrong_code_and_lockout(self):
        u = make_user()
        set_code(u["email"], "123456")
        for _ in range(5):
            r = verify(u["email"], "000000")
            assert r.status_code == 401 and r.json()["detail"] == "Incorrect code"
        r = verify(u["email"], "123456")
        assert r.status_code == 429
        assert mongo.login_otps.count_documents({"email": u["email"]}) == 0
        assert verify(u["email"], "123456").status_code == 400

    def test_success(self):
        u = make_user()
        assert mongo.users.find_one({"id": u["id"]})["email_verified"] is False
        set_code(u["email"], "654321")
        s = requests.Session()
        r = verify(u["email"], "654321", s)
        assert r.status_code == 200, r.text
        assert "password_hash" not in r.json() and "_id" not in r.json()
        assert "access_token" in s.cookies and "refresh_token" in s.cookies
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200 and me.json()["email"] == u["email"]
        assert mongo.users.find_one({"id": u["id"]})["email_verified"] is True
        # code consumed
        assert verify(u["email"], "654321").status_code == 400

    def test_expired_and_missing(self):
        u = make_user()
        assert verify(u["email"], "111111").status_code == 400
        set_code(u["email"], "111111", minutes=-1)
        assert verify(u["email"], "111111").status_code == 400

    def test_bad_format(self):
        assert verify("demo@aetheria.io", "12ab").status_code == 422

    def test_suspended(self):
        u = make_user()
        mongo.users.update_one({"id": u["id"]}, {"$set": {"status": "suspended"}})
        r = requests.post(f"{API}/auth/otp/request", json={"email": u["email"]})
        assert r.status_code == 200
        set_code(u["email"], "222222")
        r = verify(u["email"], "222222")
        assert r.status_code == 403
