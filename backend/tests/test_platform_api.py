# Aetheria credit platform - backend regression tests (auth, wallet, deposits, admin, fraud, support, settings)
import os
import uuid
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("admin@aetheria.io", "Admin@12345")
DEMO = ("demo@aetheria.io", "Demo@12345")

mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
CREATED_USER_IDS = []


def login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return s, r


def make_user(verified=True):
    s = requests.Session()
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"name": "TEST_User", "email": email, "password": "Test@12345"})
    assert r.status_code == 200, r.text
    u = r.json()
    CREATED_USER_IDS.append(u["id"])
    if verified:
        mongo.users.update_one({"id": u["id"]}, {"$set": {"email_verified": True}})
    return s, u


@pytest.fixture(scope="module")
def admin():
    return login(*ADMIN)[0]


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in CREATED_USER_IDS:
        mongo.deposits.delete_many({"user_id": uid})
        mongo.transactions.delete_many({"user_id": uid})
        mongo.tickets.delete_many({"user_id": uid})
        mongo.fraud_alerts.delete_many({"user_id": uid})
        mongo.email_tokens.delete_many({"user_id": uid})
        mongo.users.delete_one({"id": uid})


# --- Auth ---
class TestAuth:
    def test_public_config(self):
        r = requests.get(f"{API}/public/config")
        assert r.status_code == 200
        d = r.json()
        assert d["fee_percent"] == 20 and d["promo_multiplier"] == 5

    def test_login_cookies_and_me(self):
        s, r = login(*DEMO)
        sc = r.headers.get("set-cookie", "")
        assert "access_token" in sc and "refresh_token" in sc and "HttpOnly" in sc
        assert "password_hash" not in r.json() and "_id" not in r.json()
        me = s.get(f"{API}/auth/me").json()
        assert me["email"] == DEMO[0] and me["role"] == "user"

    def test_bcrypt_hash(self):
        u = mongo.users.find_one({"email": ADMIN[0]})
        assert u["password_hash"].startswith("$2b$")

    def test_cors_credentials(self):
        r = requests.options(f"{API}/auth/login", headers={"Origin": BASE_URL, "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") == BASE_URL
        assert r.headers.get("access-control-allow-credentials") == "true"

    def test_refresh(self):
        s, _ = login(*DEMO)
        refresh_tok = s.cookies.get("refresh_token")
        s = requests.Session()
        s.cookies.set("refresh_token", refresh_tok)
        assert s.get(f"{API}/auth/me").status_code == 401
        r = s.post(f"{API}/auth/refresh")
        assert r.status_code == 200
        assert "access_token" in r.headers.get("set-cookie", "")
        assert s.get(f"{API}/auth/me").status_code == 200

    def test_refresh_without_cookie(self):
        assert requests.post(f"{API}/auth/refresh").status_code == 401

    def test_register_duplicate_and_unverified_deposit(self):
        s, u = make_user(verified=False)
        assert u["email_verified"] is False
        r = s.post(f"{API}/deposits", json={"amount": 5000, "method": "upi"})
        assert r.status_code == 403 and "verify" in r.json()["detail"].lower()
        r2 = requests.post(f"{API}/auth/register", json={"name": "TEST_dup", "email": u["email"], "password": "Test@12345"})
        assert r2.status_code == 400

    def test_bad_login(self):
        r = requests.post(f"{API}/auth/login", json={"email": DEMO[0], "password": "wrong-pw"})
        assert r.status_code == 401
        # reset counter so demo isn't progressing toward lockout
        login(*DEMO)

    def test_lockout(self, admin):
        email = f"test_lock_{uuid.uuid4().hex[:6]}@example.com"
        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "x"}).status_code for _ in range(6)]
        assert codes[:5] == [401] * 5, codes
        assert codes[5] == 429, codes
        alerts = admin.get(f"{API}/admin/fraud", params={"status": "open"}).json()
        a = [x for x in alerts if x["kind"] == "login_lockout" and email in x["message"]]
        assert a
        mongo.fraud_alerts.delete_many({"id": a[0]["id"]})
        mongo.login_attempts.delete_many({"identifier": {"$regex": email}})


# --- Role protection ---
class TestRoles:
    def test_user_blocked_from_admin(self):
        s, _ = login(*DEMO)
        for p in ["stats", "users", "deposits", "settings", "fraud", "tickets", "transactions"]:
            assert s.get(f"{API}/admin/{p}").status_code == 403, p

    def test_unauth(self):
        assert requests.get(f"{API}/wallet").status_code == 401
        assert requests.get(f"{API}/admin/stats").status_code == 401

    def test_admin_cannot_deposit(self, admin):
        assert admin.post(f"{API}/deposits", json={"amount": 5000, "method": "upi"}).status_code == 403


# --- Deposits & approval ledger ---
class TestDeposits:
    def test_demo_wallet(self):
        s, _ = login(*DEMO)
        w = s.get(f"{API}/wallet").json()
        assert w["real_balance"] >= 16000 and w["promo_balance"] >= 100000

    def test_deposit_limits(self):
        s, _ = make_user()
        assert s.post(f"{API}/deposits", json={"amount": 500, "method": "upi"}).status_code == 400
        assert s.post(f"{API}/deposits", json={"amount": 600000, "method": "upi"}).status_code == 400
        assert s.post(f"{API}/deposits", json={"amount": 5000, "method": "paypal"}).status_code == 422

    def test_approve_flow(self, admin):
        s, u = make_user()
        r = s.post(f"{API}/deposits", json={"amount": 20000, "method": "upi"})
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "pending" and d["service_fee"] == 4000 and d["net_real_credit"] == 16000 and d["promo_credit"] == 100000
        assert any(x["id"] == d["id"] for x in s.get(f"{API}/deposits").json())
        pend = admin.get(f"{API}/admin/deposits", params={"status": "pending"}).json()
        assert any(x["id"] == d["id"] for x in pend)
        a = admin.post(f"{API}/admin/deposits/{d['id']}/approve")
        assert a.status_code == 200 and a.json()["status"] == "approved"
        assert admin.post(f"{API}/admin/deposits/{d['id']}/approve").status_code == 409
        w = s.get(f"{API}/wallet").json()
        assert w["real_balance"] == 16000 and w["promo_balance"] == 100000
        txs = s.get(f"{API}/transactions").json()
        kinds = sorted(t["type"] for t in txs)
        assert kinds == ["deposit", "promo_credit", "service_fee"]
        assert s.get(f"{API}/transactions", params={"wallet": "promo"}).json()[0]["amount"] == 100000
        assert len(s.get(f"{API}/transactions", params={"type": "service_fee"}).json()) == 1

    def test_reject_flow(self, admin):
        s, u = make_user()
        d = s.post(f"{API}/deposits", json={"amount": 5000, "method": "card"}).json()
        r = admin.post(f"{API}/admin/deposits/{d['id']}/reject", json={"reason": "TEST_bad proof"})
        assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["reject_reason"] == "TEST_bad proof"
        assert s.get(f"{API}/wallet").json()["real_balance"] == 0

    def test_fraud_high_amount_and_velocity(self, admin):
        s, u = make_user()
        d1 = s.post(f"{API}/deposits", json={"amount": 100000, "method": "usdt"}).json()
        assert "high_amount" in d1["fraud_flags"]
        s.post(f"{API}/deposits", json={"amount": 2000, "method": "upi"})
        d3 = s.post(f"{API}/deposits", json={"amount": 2000, "method": "upi"}).json()
        assert "velocity" in d3["fraud_flags"]
        alerts = [a for a in admin.get(f"{API}/admin/fraud").json() if a["user_id"] == u["id"]]
        kinds = {a["kind"] for a in alerts}
        assert {"high_amount", "velocity"} <= kinds
        r = admin.post(f"{API}/admin/fraud/{alerts[0]['id']}/resolve")
        assert r.status_code == 200
        res = [a for a in admin.get(f"{API}/admin/fraud", params={"status": "resolved"}).json() if a["id"] == alerts[0]["id"]]
        assert res and res[0]["status"] == "resolved"
        assert admin.post(f"{API}/admin/fraud/nonexistent/resolve").status_code == 404


# --- Admin users ---
class TestAdminUsers:
    def test_search_suspend_activate_adjust(self, admin):
        s, u = make_user()
        found = admin.get(f"{API}/admin/users", params={"q": u["email"]}).json()
        assert len(found) == 1 and "password_hash" not in found[0]
        assert admin.patch(f"{API}/admin/users/{u['id']}/status", json={"status": "suspended"}).status_code == 200
        assert s.get(f"{API}/auth/me").status_code == 403
        assert requests.post(f"{API}/auth/login", json={"email": u["email"], "password": "Test@12345"}).status_code == 403
        assert admin.patch(f"{API}/admin/users/{u['id']}/status", json={"status": "active"}).status_code == 200
        login(u["email"], "Test@12345")
        r = admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"wallet": "real", "amount": 500, "reason": "TEST_bonus"})
        assert r.status_code == 200 and r.json()["real_balance"] == 500
        r = admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"wallet": "real", "amount": -1000, "reason": "TEST_over"})
        assert r.status_code == 400
        r = admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"wallet": "real", "amount": -200, "reason": "TEST_ded"})
        assert r.status_code == 200 and r.json()["real_balance"] == 300
        assert admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"wallet": "real", "amount": 0, "reason": "TEST_z"}).status_code == 400

    def test_admin_self_status(self, admin):
        me = admin.get(f"{API}/auth/me").json()
        assert admin.patch(f"{API}/admin/users/{me['id']}/status", json={"status": "suspended"}).status_code == 400

    def test_stats(self, admin):
        st = admin.get(f"{API}/admin/stats").json()
        assert len(st["series"]) == 30 and "total_fees" in st and "pending_count" in st


# --- Settings ---
class TestSettings:
    def test_update_and_restore(self, admin):
        orig = admin.get(f"{API}/admin/settings").json()
        body = {k: orig[k] for k in ("fee_percent", "promo_multiplier", "min_deposit", "max_deposit",
                                     "fraud_amount_threshold", "fraud_velocity_count", "packages")}
        try:
            bad = dict(body, min_deposit=10000, max_deposit=5000)
            assert admin.put(f"{API}/admin/settings", json=bad).status_code == 400
            r = admin.put(f"{API}/admin/settings", json=dict(body, fee_percent=10, promo_multiplier=3))
            assert r.status_code == 200 and r.json()["fee_percent"] == 10
            s, _ = make_user()
            d = s.post(f"{API}/deposits", json={"amount": 10000, "method": "upi"}).json()
            assert d["service_fee"] == 1000 and d["promo_credit"] == 30000
        finally:
            r = admin.put(f"{API}/admin/settings", json=body)
            assert r.status_code == 200 and r.json()["fee_percent"] == 20 and r.json()["promo_multiplier"] == 5


# --- Support ---
class TestSupport:
    def test_ticket_flow(self, admin):
        s, u = make_user()
        r = s.post(f"{API}/support/tickets", json={"subject": "TEST_ticket", "category": "deposit", "message": "Help me please"})
        assert r.status_code == 200
        t = r.json()
        assert s.post(f"{API}/support/tickets/{t['id']}/reply", json={"message": "more"}).json()["messages"][-1]["message"] == "more"
        assert any(x["id"] == t["id"] for x in admin.get(f"{API}/admin/tickets").json())
        ar = admin.post(f"{API}/admin/tickets/{t['id']}/reply", json={"message": "admin reply"}).json()
        assert ar["messages"][-1]["author_role"] == "admin"
        st = admin.patch(f"{API}/admin/tickets/{t['id']}/status", json={"status": "resolved"}).json()
        assert st["status"] == "resolved"
        mine = s.get(f"{API}/support/tickets").json()
        assert mine[0]["status"] == "resolved" and len(mine[0]["messages"]) == 3
        # other user cannot reply to this ticket
        s2, _ = make_user()
        assert s2.post(f"{API}/support/tickets/{t['id']}/reply", json={"message": "x"}).status_code == 404
