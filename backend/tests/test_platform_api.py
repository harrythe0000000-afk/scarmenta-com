# Aetheria credit platform - backend regression tests (single 5X credit balance, no fee, no withdrawals; auth, deposits, admin, fraud, support, settings)
import os
import uuid
from datetime import datetime, timedelta, timezone
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
CREATED_PROVIDER_IDS = []


def login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return s, r


def make_user(verified=True, ref=None):
    s = requests.Session()
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    body = {"name": "TEST_User", "email": email, "password": "Test@12345"}
    if ref:
        body["referral_code"] = ref
    r = s.post(f"{API}/auth/register", json=body)
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
        mongo.game_transactions.delete_many({"user_id": uid})
        mongo.game_sessions.delete_many({"user_id": uid})
        mongo.users.delete_one({"id": uid})
    for pid in CREATED_PROVIDER_IDS:
        mongo.game_transactions.delete_many({"provider_id": pid})
        mongo.game_sessions.delete_many({"provider_id": pid})
        mongo.providers.delete_one({"id": pid})


# --- Auth ---
class TestAuth:
    def test_public_config(self):
        r = requests.get(f"{API}/public/config")
        assert r.status_code == 200
        d = r.json()
        assert "fee_percent" not in d and d["promo_multiplier"] == 5
        assert all(d["min_deposit"] <= p <= d["max_deposit"] for p in d["packages"])

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
        assert codes[:4] == [401] * 4, codes
        assert codes[4] == 429 and codes[5] == 429, codes
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
        assert set(w) == {"balance", "total_deposited", "total_credits", "approved_count", "pending_count"}, w
        # balance may drift from 100000 because of game activity on demo; it must match the latest ledger entry
        last = s.get(f"{API}/transactions").json()[0]
        assert w["balance"] == last["balance_after"] and w["total_deposited"] == 20000 and w["total_credits"] == 100000 and w["pending_count"] == 1

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
        assert d["status"] == "pending" and d["promo_credit"] == 100000 and d["promo_multiplier"] == 5
        assert "service_fee" not in d and "net_real_credit" not in d
        assert any(x["id"] == d["id"] for x in s.get(f"{API}/deposits").json())
        pend = admin.get(f"{API}/admin/deposits", params={"status": "pending"}).json()
        assert any(x["id"] == d["id"] for x in pend)
        a = admin.post(f"{API}/admin/deposits/{d['id']}/approve")
        assert a.status_code == 200 and a.json()["status"] == "approved"
        assert admin.post(f"{API}/admin/deposits/{d['id']}/approve").status_code == 409
        w = s.get(f"{API}/wallet").json()
        # balance may drift from 100000 because of game activity on demo; it must match the latest ledger entry
        last = s.get(f"{API}/transactions").json()[0]
        assert w["balance"] == last["balance_after"] and w["total_deposited"] == 20000 and w["total_credits"] == 100000 and w["pending_count"] == 0
        txs = s.get(f"{API}/transactions").json()
        assert len(txs) == 1, txs
        assert txs[0]["type"] == "deposit" and txs[0]["wallet"] == "credit" and txs[0]["amount"] == 100000 and txs[0]["balance_after"] == 100000
        assert len(s.get(f"{API}/transactions", params={"type": "service_fee"}).json()) == 0
        assert len(s.get(f"{API}/transactions", params={"type": "deposit"}).json()) == 1
        assert mongo.transactions.count_documents({"type": "service_fee", "user_id": u["id"]}) == 0

    def test_reject_flow(self, admin):
        s, u = make_user()
        d = s.post(f"{API}/deposits", json={"amount": 5000, "method": "card"}).json()
        r = admin.post(f"{API}/admin/deposits/{d['id']}/reject", json={"reason": "TEST_bad proof"})
        assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["reject_reason"] == "TEST_bad proof"
        assert s.get(f"{API}/wallet").json()["balance"] == 0
        assert s.get(f"{API}/transactions").json() == []

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

    def test_settings_update_and_restore(self, admin):
        orig = admin.get(f"{API}/admin/settings").json()
        body = {k: orig[k] for k in ("promo_multiplier", "min_deposit", "max_deposit", "fraud_amount_threshold",
                                     "fraud_velocity_count", "referral_bonus_percent", "packages")}
        try:
            assert admin.put(f"{API}/admin/settings", json=dict(body, min_deposit=10000, max_deposit=5000)).status_code == 400
            assert admin.put(f"{API}/admin/settings", json=dict(body, packages=[500])).status_code == 400
            assert admin.put(f"{API}/admin/settings", json=dict(body, promo_multiplier=11)).status_code == 422
            r = admin.put(f"{API}/admin/settings", json=dict(body, promo_multiplier=4))
            assert r.status_code == 200 and r.json()["promo_multiplier"] == 4
            assert requests.get(f"{API}/public/config").json()["promo_multiplier"] == 4
            s, _ = make_user()
            d = s.post(f"{API}/deposits", json={"amount": 10000, "method": "upi"}).json()
            assert d["promo_credit"] == 40000 and d["promo_multiplier"] == 4
        finally:
            r = admin.put(f"{API}/admin/settings", json=dict(body, promo_multiplier=5))
            assert r.status_code == 200 and r.json()["promo_multiplier"] == 5


    # --- Refer & Earn (kept in TestDeposits so settings changes don't race under xdist loadscope) ---
    def test_referral_invalid_code(self):
        r = requests.post(f"{API}/auth/register", json={"name": "TEST_x", "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
                                                         "password": "Test@12345", "referral_code": "ZZZZZZ"})
        assert r.status_code == 400 and r.json()["detail"] == "Invalid referral code"

    def test_referral_bonus_once(self, admin):
        rs, ru = make_user()
        me = rs.get(f"{API}/referrals/me").json()
        assert me["code"] == ru["referral_code"] and me["link"].endswith(f"/register?ref={me['code']}")
        assert me["bonus_percent"] == 10 and me["total_referred"] == 0
        es, eu = make_user(ref=me["code"].lower())  # case-insensitive
        assert rs.get(f"{API}/referrals/me").json()["referrals"][0]["status"] == "pending"
        d1 = es.post(f"{API}/deposits", json={"amount": 10000, "method": "upi"}).json()
        assert admin.post(f"{API}/admin/deposits/{d1['id']}/approve").status_code == 200
        assert rs.get(f"{API}/wallet").json()["balance"] == 1000
        txs = rs.get(f"{API}/transactions").json()
        assert len(txs) == 1 and txs[0]["type"] == "referral_bonus" and txs[0]["amount"] == 1000 and txs[0]["balance_after"] == 1000
        d2 = es.post(f"{API}/deposits", json={"amount": 5000, "method": "upi"}).json()
        assert admin.post(f"{API}/admin/deposits/{d2['id']}/approve").status_code == 200
        assert rs.get(f"{API}/wallet").json()["balance"] == 1000
        assert len(rs.get(f"{API}/transactions").json()) == 1
        assert es.get(f"{API}/wallet").json()["balance"] == 75000  # referee gets no bonus, only 5X
        me = rs.get(f"{API}/referrals/me").json()
        assert me["total_referred"] == 1 and me["total_earned"] == 1000 and me["referrals"][0]["status"] == "rewarded"
        assert "@" not in me["referrals"][0]["name"]
        adm = admin.get(f"{API}/admin/referrals", params={"status": "rewarded"}).json()
        row = [x for x in adm if x["email"] == eu["email"]]
        assert row and row[0]["reward"] == 1000 and row[0]["referred_by_email"] == ru["email"]
        assert not [x for x in admin.get(f"{API}/admin/referrals", params={"status": "pending"}).json() if x["email"] == eu["email"]]
        assert rs.get(f"{API}/admin/referrals").status_code == 403

    def test_referral_zero_percent(self, admin):
        orig = admin.get(f"{API}/admin/settings").json()
        body = {k: orig[k] for k in ("promo_multiplier", "min_deposit", "max_deposit", "fraud_amount_threshold",
                                     "fraud_velocity_count", "referral_bonus_percent", "packages")}
        try:
            assert admin.put(f"{API}/admin/settings", json=dict(body, referral_bonus_percent=101)).status_code == 422
            r = admin.put(f"{API}/admin/settings", json=dict(body, referral_bonus_percent=0))
            assert r.status_code == 200 and r.json()["referral_bonus_percent"] == 0
            rs, ru = make_user()
            es, eu = make_user(ref=ru["referral_code"])
            d = es.post(f"{API}/deposits", json={"amount": 10000, "method": "upi"}).json()
            assert admin.post(f"{API}/admin/deposits/{d['id']}/approve").status_code == 200
            assert rs.get(f"{API}/wallet").json()["balance"] == 0
            assert rs.get(f"{API}/transactions").json() == []
        finally:
            r = admin.put(f"{API}/admin/settings", json=dict(body, promo_multiplier=5, referral_bonus_percent=10))
            assert r.status_code == 200 and r.json()["referral_bonus_percent"] == 10


# --- Logout ---
class TestLogout:
    @pytest.mark.parametrize("creds", [DEMO, ADMIN])
    def test_logout(self, creds):
        s, _ = login(*creds)
        assert s.get(f"{API}/auth/me").status_code == 200
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        sc = r.headers.get("set-cookie", "")
        assert "access_token" in sc and "refresh_token" in sc
        assert s.get(f"{API}/auth/me").status_code == 401
        assert s.post(f"{API}/auth/refresh").status_code == 401


# --- Game providers & seamless wallet ---
def make_provider(admin, **kw):
    code = f"t{uuid.uuid4().hex[:8]}"
    body = {"name": f"TEST_Prov {code}", "code": code, "launch_url": None, "description": "TEST", "status": "active", **kw}
    r = admin.post(f"{API}/admin/providers", json=body)
    assert r.status_code == 200, r.text
    p = r.json()
    CREATED_PROVIDER_IDS.append(p["id"])
    return p


class TestProviders:
    def test_admin_provider_crud_and_rotate(self, admin):
        p = make_provider(admin, status="inactive")
        assert p["api_key"].startswith("pk_") and "api_key_hash" not in p and p["api_key_last4"] == p["api_key"][-4:]
        listed = [x for x in admin.get(f"{API}/admin/providers").json() if x["id"] == p["id"]]
        assert listed and "api_key" not in listed[0] and "api_key_hash" not in listed[0]
        base = {"name": p["name"], "code": p["code"], "description": "x", "status": "inactive"}
        assert admin.post(f"{API}/admin/providers", json=dict(base, launch_url=None)).status_code == 400
        assert admin.post(f"{API}/admin/providers", json=dict(base, code=f"t{uuid.uuid4().hex[:8]}",
                                                               launch_url="http://evil.example")).status_code == 400
        assert admin.post(f"{API}/admin/providers", json=dict(base, code="BAD CODE")).status_code == 422
        r = admin.put(f"{API}/admin/providers/{p['id']}", json=dict(base, name="TEST_Renamed", launch_url="https://games.example.com/play?x=1"))
        assert r.status_code == 200 and r.json()["name"] == "TEST_Renamed" and "api_key_hash" not in r.json()
        assert admin.put(f"{API}/admin/providers/{p['id']}", json=dict(base, launch_url="ftp://x")).status_code == 400
        assert admin.put(f"{API}/admin/providers/nonexistent", json=dict(base, code=f"t{uuid.uuid4().hex[:8]}")).status_code == 404
        # inactive provider: hidden and wallet 401
        s, _ = make_user()
        assert not [x for x in s.get(f"{API}/games/providers").json() if x["id"] == p["id"]]
        assert requests.post(f"{API}/provider/v1/balance", headers={"X-Provider-Key": p["api_key"]},
                             json={"session_token": "x"}).status_code == 401
        assert s.post(f"{API}/games/launch", json={"provider_id": p["id"]}).status_code == 404
        # activate + rotate
        admin.put(f"{API}/admin/providers/{p['id']}", json=dict(base, name="TEST_Renamed", launch_url="https://games.example.com/play?x=1", status="active"))
        sess = s.post(f"{API}/games/launch", json={"provider_id": p["id"]}).json()
        assert sess["launch_url"].startswith("https://games.example.com/play?x=1&token=") and "currency=INR" in sess["launch_url"]
        old = p["api_key"]
        assert requests.post(f"{API}/provider/v1/balance", headers={"X-Provider-Key": old},
                             json={"session_token": sess["session_token"]}).status_code == 200
        rk = admin.post(f"{API}/admin/providers/{p['id']}/rotate-key").json()
        assert rk["api_key"] != old and rk["api_key"].startswith("pk_")
        assert requests.post(f"{API}/provider/v1/balance", headers={"X-Provider-Key": old},
                             json={"session_token": sess["session_token"]}).status_code == 401
        assert requests.post(f"{API}/provider/v1/balance", headers={"X-Provider-Key": rk["api_key"]},
                             json={"session_token": sess["session_token"]}).status_code == 200
        assert admin.post(f"{API}/admin/providers/nonexistent/rotate-key").status_code == 404
        assert s.get(f"{API}/admin/providers").status_code == 403

    def test_launch_rules(self, admin):
        p = make_provider(admin)
        s, _ = make_user()
        pl = [x for x in s.get(f"{API}/games/providers").json() if x["id"] == p["id"]]
        assert pl and pl[0]["connected"] is False and "launch_url" not in pl[0]
        r = s.post(f"{API}/games/launch", json={"provider_id": p["id"]}).json()
        assert r["launch_url"] is None and len(r["session_token"]) > 20
        assert admin.post(f"{API}/games/launch", json={"provider_id": p["id"]}).status_code == 403
        assert requests.post(f"{API}/games/launch", json={"provider_id": p["id"]}).status_code == 401

    def test_wallet_flow(self, admin):
        p = make_provider(admin)
        H = {"X-Provider-Key": p["api_key"]}
        s, u = make_user()
        admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"amount": 1000, "reason": "TEST_fund"})
        tok = s.post(f"{API}/games/launch", json={"provider_id": p["id"]}).json()["session_token"]
        pv = lambda ep, **b: requests.post(f"{API}/provider/v1/{ep}", headers=H, json={"session_token": tok, **b})
        assert requests.post(f"{API}/provider/v1/balance", json={"session_token": tok}).status_code == 401
        assert pv("balance").json()["balance"] == 1000
        assert requests.post(f"{API}/provider/v1/balance", headers=H, json={"session_token": "bogus"}).status_code == 401
        b = pv("bet", transaction_id="b1", round_id="r1", amount=300, game_code="roulette")
        assert b.status_code == 200 and b.json()["status"] == "ok" and b.json()["balance"] == 700 and b.json()["duplicate"] is False
        dup = pv("bet", transaction_id="b1", round_id="r1", amount=300)
        assert dup.json()["duplicate"] is True and dup.json()["balance"] == 700
        assert pv("balance").json()["balance"] == 700
        nf = pv("bet", transaction_id="b2", round_id="r2", amount=5000)
        assert nf.status_code == 402 and nf.json()["detail"] == "INSUFFICIENT_FUNDS"
        assert pv("balance").json()["balance"] == 700
        assert pv("bet", transaction_id="b0", round_id="r1", amount=0).status_code == 422
        nb = pv("win", transaction_id="w0", round_id="nope", amount=100)
        assert nb.status_code == 400 and nb.json()["detail"] == "NO_BET_FOR_ROUND"
        w = pv("win", transaction_id="w1", round_id="r1", amount=900)
        assert w.status_code == 200 and w.json()["balance"] == 1600
        assert pv("win", transaction_id="w1", round_id="r1", amount=900).json()["duplicate"] is True
        assert pv("balance").json()["balance"] == 1600
        pv("bet", transaction_id="b3", round_id="r3", amount=200)
        rb = pv("rollback", transaction_id="rb1", ref_transaction_id="b3")
        assert rb.status_code == 200 and rb.json()["balance"] == 1600
        assert pv("rollback", transaction_id="rb1", ref_transaction_id="b3").json()["duplicate"] is True
        assert pv("rollback", transaction_id="rb2", ref_transaction_id="b3").status_code == 404
        assert pv("rollback", transaction_id="rb3", ref_transaction_id="missing").status_code == 404
        assert s.get(f"{API}/wallet").json()["balance"] == 1600
        # ledger: adjust + bet b1 + win + bet b3 + rollback
        txs = s.get(f"{API}/transactions").json()
        kinds = sorted(t["type"] for t in txs)
        assert kinds == ["admin_adjustment", "bet", "bet", "rollback", "win"], kinds
        assert txs[0]["balance_after"] == 1600
        bets = [t for t in txs if t["type"] == "bet"]
        assert all(t["amount"] < 0 for t in bets)
        hist = s.get(f"{API}/games/history").json()
        hist_statuses = [h["status"] for h in hist]
        # admin stats & tx list
        st = admin.get(f"{API}/admin/game-stats").json()
        row = [x for x in st["providers"] if x["provider_id"] == p["id"]][0]
        assert row["bets"] == 500 and row["wins"] == 900 and row["rollbacks"] == 200 and row["ggr"] == -600 and row["bet_count"] == 2
        assert st["active_sessions"] >= 1
        gt = admin.get(f"{API}/admin/game-transactions", params={"provider_id": p["id"], "type": "bet"}).json()
        assert len(gt) == 3  # incl. insufficient_funds attempt
        assert len(admin.get(f"{API}/admin/game-transactions", params={"provider_id": p["id"], "q": "r3"}).json()) == 2
        # expired session
        mongo.game_sessions.update_one({"token": tok}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}})
        assert pv("balance").status_code == 401
        # other provider cannot use this session
        p2 = make_provider(admin)
        tok2 = s.post(f"{API}/games/launch", json={"provider_id": p["id"]}).json()["session_token"]
        assert requests.post(f"{API}/provider/v1/balance", headers={"X-Provider-Key": p2["api_key"]}, json={"session_token": tok2}).status_code == 401
        # suspended player
        admin.patch(f"{API}/admin/users/{u['id']}/status", json={"status": "suspended"})
        r = requests.post(f"{API}/provider/v1/bet", headers=H, json={"session_token": tok2, "transaction_id": "b9", "round_id": "r9", "amount": 10})
        assert r.status_code == 403
        admin.patch(f"{API}/admin/users/{u['id']}/status", json={"status": "active"})
        assert all(x == "ok" for x in hist_statuses), f"failed bets must be hidden from player history: {hist_statuses}"


# --- No withdrawals ---
class TestNoWithdraw:
    def test_no_withdraw_endpoints(self):
        s, _ = login(*DEMO)
        for p in ["withdraw", "withdrawals", "wallet/withdraw"]:
            assert s.post(f"{API}/{p}", json={"amount": 100}).status_code in (404, 405), p
        paths = requests.get(f"{BASE_URL}/api/openapi.json")
        if paths.status_code == 200:
            assert not any("withdraw" in k for k in paths.json().get("paths", {}))


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
        r = admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"amount": 500, "reason": "TEST_bonus"})
        assert r.status_code == 200 and r.json()["promo_balance"] == 500
        r = admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"amount": -1000, "reason": "TEST_over"})
        assert r.status_code == 400
        r = admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"amount": -200, "reason": "TEST_ded"})
        assert r.status_code == 200 and r.json()["promo_balance"] == 300
        assert s.get(f"{API}/wallet").json()["balance"] == 300
        txs = s.get(f"{API}/transactions", params={"type": "admin_adjustment"}).json()
        assert len(txs) == 2 and all(t["wallet"] == "credit" for t in txs) and txs[0]["balance_after"] == 300
        assert admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"amount": 0, "reason": "TEST_z"}).status_code == 400
        assert admin.post(f"{API}/admin/users/nonexistent/adjust", json={"amount": 10, "reason": "TEST_n"}).status_code == 400
        me = admin.get(f"{API}/auth/me").json()
        assert admin.post(f"{API}/admin/users/{me['id']}/adjust", json={"amount": 10, "reason": "TEST_adm"}).status_code == 400

    def test_admin_self_status(self, admin):
        me = admin.get(f"{API}/auth/me").json()
        assert admin.patch(f"{API}/admin/users/{me['id']}/status", json={"status": "suspended"}).status_code == 400

    def test_stats(self, admin):
        st = admin.get(f"{API}/admin/stats").json()
        assert len(st["series"]) == 30 and "total_fees" not in st and "pending_count" in st
        for k in ("total_deposits", "total_credits", "credit_outstanding"):
            assert isinstance(st[k], (int, float)), k
        assert set(st["series"][0]) == {"date", "deposits", "credits"}


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
        ar2 = admin.post(f"{API}/admin/tickets/{t['id']}/reply", json={"message": "admin reply 2"}).json()
        assert ar2["status"] == "resolved"
        mine = s.get(f"{API}/support/tickets").json()
        assert mine[0]["status"] == "resolved" and len(mine[0]["messages"]) == 4
        # other user cannot reply to this ticket
        s2, _ = make_user()
        assert s2.post(f"{API}/support/tickets/{t['id']}/reply", json={"message": "x"}).status_code == 404
