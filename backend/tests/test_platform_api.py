# Aetheria credit platform - backend regression tests (USD model: 5X single credit balance, USDT/UPI deposits with
# payment reference + admin approval, FX rates, referral 10% on every deposit, weekly loss rewards, money flow,
# provider seamless wallet, auth, admin, fraud, support)
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
SETTINGS_KEYS = ("promo_multiplier", "min_deposit", "max_deposit", "fraud_amount_threshold", "fraud_velocity_count",
                 "referral_bonus_percent", "loss_reward_percent", "packages", "fx_rates", "upi_id", "usdt_trc20",
                 "usdt_erc20", "usdt_bep20")

mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
CREATED_USER_IDS = []
CREATED_PROVIDER_IDS = []


def ref():
    return f"TEST{uuid.uuid4().hex[:12].upper()}"


def login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return s, r


def make_user(verified=True, ref_code=None):
    s = requests.Session()
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    body = {"name": "TEST User", "email": email, "password": "Test@12345"}
    if ref_code:
        body["referral_code"] = ref_code
    r = s.post(f"{API}/auth/register", json=body)
    assert r.status_code == 200, r.text
    u = r.json()
    CREATED_USER_IDS.append(u["id"])
    if verified:
        mongo.users.update_one({"id": u["id"]}, {"$set": {"email_verified": True}})
    return s, u


def usdt(amount, network="TRC20"):
    return {"amount": amount, "method": "usdt", "network": network, "payment_reference": ref()}


def upi(amount):
    return {"amount": amount, "method": "upi", "payment_reference": ref()}


def settings_body(admin):
    orig = admin.get(f"{API}/admin/settings").json()
    return {k: orig[k] for k in SETTINGS_KEYS}


@pytest.fixture(scope="module")
def admin():
    return login(*ADMIN)[0]


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in CREATED_USER_IDS:
        for c in ("deposits", "transactions", "tickets", "fraud_alerts", "email_tokens", "game_transactions", "game_sessions"):
            mongo[c].delete_many({"user_id": uid})
        mongo.users.delete_one({"id": uid})
    for pid in CREATED_PROVIDER_IDS:
        mongo.game_transactions.delete_many({"provider_id": pid})
        mongo.game_sessions.delete_many({"provider_id": pid})
        mongo.providers.delete_one({"id": pid})


def make_provider(admin, **kw):
    code = f"t{uuid.uuid4().hex[:8]}"
    body = {"name": f"TEST_Prov {code}", "code": code, "launch_url": None, "description": "TEST", "status": "active", **kw}
    r = admin.post(f"{API}/admin/providers", json=body)
    assert r.status_code == 200, r.text
    p = r.json()
    CREATED_PROVIDER_IDS.append(p["id"])
    return p


# --- Auth ---
class TestAuth:
    def test_public_config(self):
        d = requests.get(f"{API}/public/config").json()
        assert d["currency"] == "USD" and d["promo_multiplier"] == 5
        assert d["packages"] == [50, 100, 250, 500, 1000]
        assert d["fx_rates"]["INR"] == 95 and set(d["payment"]["usdt"]) == {"TRC20", "ERC20", "BEP20"}

    def test_login_cookies_and_me(self):
        s, r = login(*DEMO)
        sc = r.headers.get("set-cookie", "")
        assert "access_token" in sc and "refresh_token" in sc and "HttpOnly" in sc
        assert "password_hash" not in r.json() and "_id" not in r.json()
        assert s.get(f"{API}/auth/me").json()["role"] == "user"

    def test_bcrypt_and_cors(self):
        assert mongo.users.find_one({"email": ADMIN[0]})["password_hash"].startswith("$2b$")
        r = requests.options(f"{API}/auth/login", headers={"Origin": BASE_URL, "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") == BASE_URL
        assert r.headers.get("access-control-allow-credentials") == "true"

    def test_unverified_cannot_deposit(self):
        s, u = make_user(verified=False)
        r = s.post(f"{API}/deposits", json=usdt(100))
        assert r.status_code == 403 and "verify" in r.json()["detail"].lower()

    def test_lockout(self, admin):
        email = f"test_lock_{uuid.uuid4().hex[:6]}@example.com"
        codes = [requests.post(f"{API}/auth/login", json={"email": email, "password": "x"}).status_code for _ in range(6)]
        assert codes[:4] == [401] * 4 and codes[4] == 429 and codes[5] == 429, codes
        mongo.fraud_alerts.delete_many({"kind": "login_lockout", "message": {"$regex": email}})
        mongo.login_attempts.delete_many({"identifier": f"email:{email}"})

    @pytest.mark.parametrize("creds", [DEMO, ADMIN])
    def test_logout(self, creds):
        s, _ = login(*creds)
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        assert s.get(f"{API}/auth/me").status_code == 401
        assert s.post(f"{API}/auth/refresh").status_code == 401

    def test_roles(self, admin):
        s, _ = login(*DEMO)
        for p in ["stats", "users", "deposits", "settings", "fraud", "money-flow", "loss-rewards/preview", "referrals"]:
            assert s.get(f"{API}/admin/{p}").status_code == 403, p
        assert admin.post(f"{API}/deposits", json=usdt(100)).status_code == 403


# --- Deposits, settings, referral, loss rewards (one class: shared settings) ---
class TestDeposits:
    def test_usdt_and_upi_deposit(self, admin):
        s, u = make_user()
        r = s.post(f"{API}/deposits", json=usdt(200))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["currency"] == "USD" and d["network"] == "TRC20" and d["local_currency"] == "USDT" and d["promo_credit"] == 1000
        r = s.post(f"{API}/deposits", json=upi(100))
        assert r.status_code == 200, r.text
        d2 = r.json()
        assert d2["local_currency"] == "INR" and d2["fx_rate"] == 95 and d2["local_amount"] == 9500 and d2["network"] is None
        a = admin.post(f"{API}/admin/deposits/{d['id']}/approve")
        assert a.status_code == 200
        assert admin.post(f"{API}/admin/deposits/{d['id']}/approve").status_code == 409
        w = s.get(f"{API}/wallet").json()
        assert w["balance"] == 1000 and w["total_deposited"] == 200 and w["pending_count"] == 1
        tx = s.get(f"{API}/transactions").json()[0]
        assert tx["type"] == "deposit" and tx["amount"] == 1000 and "$200.00" in tx["description"] and "TRC20" in tx["description"]
        adm = [x for x in admin.get(f"{API}/admin/deposits").json() if x["id"] == d2["id"]][0]
        assert adm["payment_reference"] and adm["local_amount"] == 9500

    def test_deposit_validation(self):
        s, _ = make_user()
        dup = ref()
        assert s.post(f"{API}/deposits", json=dict(usdt(100), payment_reference=dup)).status_code == 200
        r = s.post(f"{API}/deposits", json=dict(upi(100), payment_reference=dup))
        assert r.status_code == 400 and "already" in r.json()["detail"]
        assert s.post(f"{API}/deposits", json={"amount": 100, "method": "usdt", "payment_reference": ref()}).status_code == 400
        assert s.post(f"{API}/deposits", json=usdt(100, "ERC20")).status_code == 400
        assert s.post(f"{API}/deposits", json=usdt(100, "BEP20")).status_code == 400
        assert s.post(f"{API}/deposits", json=dict(usdt(100), payment_reference="abc")).status_code == 422
        assert s.post(f"{API}/deposits", json=usdt(5)).status_code == 400
        assert s.post(f"{API}/deposits", json=usdt(20000)).status_code == 400
        assert s.post(f"{API}/deposits", json=dict(usdt(100), method="paypal")).status_code == 422

    def test_reject_and_fraud(self, admin):
        s, u = make_user()
        d = s.post(f"{API}/deposits", json=usdt(2000)).json()
        assert "high_amount" in d["fraud_flags"]
        s.post(f"{API}/deposits", json=upi(50))
        d3 = s.post(f"{API}/deposits", json=upi(50)).json()
        assert "velocity" in d3["fraud_flags"]
        kinds = {a["kind"] for a in admin.get(f"{API}/admin/fraud").json() if a["user_id"] == u["id"]}
        assert {"high_amount", "velocity"} <= kinds
        r = admin.post(f"{API}/admin/deposits/{d['id']}/reject", json={"reason": "TEST_bad"})
        assert r.status_code == 200 and r.json()["status"] == "rejected"
        # rejected reference can be reused
        assert s.post(f"{API}/deposits", json=dict(usdt(100), payment_reference=d["payment_reference"])).status_code == 200

    def test_fx_settings(self, admin):
        body = settings_body(admin)
        try:
            bad = dict(body, fx_rates={**body["fx_rates"], "inr": 0})
            assert admin.put(f"{API}/admin/settings", json=bad).status_code == 400
            assert admin.put(f"{API}/admin/settings", json=dict(body, fx_rates={**body["fx_rates"], "X1": 3})).status_code == 400
            r = admin.put(f"{API}/admin/settings", json=dict(body, fx_rates={**body["fx_rates"], "INR": 90, "eur": 0.92},
                                                            loss_reward_percent=5, referral_bonus_percent=10))
            assert r.status_code == 200 and r.json()["fx_rates"]["INR"] == 90 and r.json()["fx_rates"]["EUR"] == 0.92
            s, _ = make_user()
            d = s.post(f"{API}/deposits", json=upi(100)).json()
            assert d["fx_rate"] == 90 and d["local_amount"] == 9000
            rates = dict(body["fx_rates"])
            rates.pop("INR")
            r = admin.put(f"{API}/admin/settings", json=dict(body, fx_rates=rates))
            assert "INR" not in r.json()["fx_rates"]
            assert s.post(f"{API}/deposits", json=upi(100)).status_code == 400
            assert admin.put(f"{API}/admin/settings", json=dict(body, min_deposit=500, max_deposit=100)).status_code == 400
        finally:
            r = admin.put(f"{API}/admin/settings", json=body)
            assert r.status_code == 200 and r.json()["fx_rates"]["INR"] == 95 and "EUR" not in r.json()["fx_rates"]
            assert r.json()["upi_id"] == body["upi_id"] and r.json()["usdt_trc20"] == body["usdt_trc20"]

    def test_referral_every_deposit(self, admin):
        rs, ru = make_user()
        code = rs.get(f"{API}/referrals/me").json()["code"]
        es, eu = make_user(ref_code=code.lower())
        assert rs.get(f"{API}/referrals/me").json()["referrals"][0]["status"] == "pending"
        for amt in (100, 50):
            d = es.post(f"{API}/deposits", json=usdt(amt)).json()
            assert admin.post(f"{API}/admin/deposits/{d['id']}/approve").status_code == 200
        w = rs.get(f"{API}/wallet").json()
        assert w["balance"] == 15 and w["referral_earnings"] == 15
        txs = rs.get(f"{API}/transactions", params={"type": "referral_bonus"}).json()
        assert sorted(t["amount"] for t in txs) == [5, 10]
        assert es.get(f"{API}/wallet").json()["balance"] == 750
        me = rs.get(f"{API}/referrals/me").json()
        assert me["total_earned"] == 15 and me["referrals"][0]["status"] == "earning"
        row = [x for x in admin.get(f"{API}/admin/referrals", params={"status": "earning"}).json() if x["email"] == eu["email"]]
        assert row and row[0]["reward"] == 15
        urow = [x for x in admin.get(f"{API}/admin/users", params={"q": ru["email"]}).json()][0]
        assert urow["referral_earnings"] == 15

    def test_loss_rewards(self, admin):
        p = make_provider(admin)
        H = {"X-Provider-Key": p["api_key"]}
        s, u = make_user()
        admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"amount": 500, "reason": "TEST_fund"})
        tok = s.post(f"{API}/games/launch", json={"provider_id": p["id"]}).json()["session_token"]
        pv = lambda ep, **b: requests.post(f"{API}/provider/v1/{ep}", headers=H, json={"session_token": tok, **b})
        assert pv("bet", transaction_id="lb1", round_id="lr1", amount=100).status_code == 200
        assert pv("win", transaction_id="lw1", round_id="lr1", amount=20).json()["balance"] == 420
        me = s.get(f"{API}/rewards/loss/me").json()
        assert me["net_loss"] == 80 and me["percent"] == 5 and me["estimated_reward"] == 4
        prev = admin.get(f"{API}/admin/loss-rewards/preview").json()
        row = [r for r in prev["rows"] if r["user_id"] == u["id"]]
        assert row and row[0]["reward"] == 4
        r = admin.post(f"{API}/admin/loss-rewards/run", json={"start": prev["start"], "end": prev["end"]})
        assert r.status_code == 200, r.text
        run = r.json()
        assert s.get(f"{API}/wallet").json()["balance"] == 424
        lt = s.get(f"{API}/transactions", params={"type": "loss_reward"}).json()
        assert len(lt) == 1 and lt[0]["amount"] == 4
        assert any(x["id"] == run["id"] for x in admin.get(f"{API}/admin/loss-rewards/runs").json())
        assert admin.post(f"{API}/admin/loss-rewards/run", json={"start": prev["start"], "end": prev["end"]}).status_code == 400
        nxt = admin.get(f"{API}/admin/loss-rewards/preview").json()
        assert nxt["start"] == run["period_end"]
        me = s.get(f"{API}/rewards/loss/me").json()
        assert me["total_received"] == 4 and len(me["history"]) == 1 and me["net_loss"] == 0
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        assert admin.post(f"{API}/admin/loss-rewards/run", json={"start": run["period_end"], "end": future}).status_code == 400

    def test_money_flow(self, admin):
        m = admin.get(f"{API}/admin/money-flow")
        assert m.status_code == 200
        d = m.json()
        for k in ("cash_in", "cash_in_usdt", "cash_in_upi", "cash_in_upi_inr", "credits_issued", "referral_paid",
                  "loss_rewards_paid", "bets", "wins", "refunds", "ggr", "outstanding"):
            assert isinstance(d[k], (int, float)), k
        assert round(d["cash_in_usdt"] + d["cash_in_upi"], 2) == d["cash_in"]
        assert d["ggr"] == round(d["bets"] - d["refunds"] - d["wins"], 2)


# --- Game providers & seamless wallet ---
class TestProviders:
    def test_seeded_providers_in_lobby(self):
        s, _ = login(*DEMO)
        lob = {x["code"]: x for x in s.get(f"{API}/games/providers").json()}
        for c in ("evolution", "ezugi", "pragmatic"):
            assert c in lob and lob[c]["connected"] is False

    def test_rotate_and_launch_usd(self, admin):
        p = make_provider(admin, launch_url="https://games.example.com/play?x=1")
        s, _ = make_user()
        sess = s.post(f"{API}/games/launch", json={"provider_id": p["id"]}).json()
        assert "currency=USD" in sess["launch_url"]
        bal = requests.post(f"{API}/provider/v1/balance", headers={"X-Provider-Key": p["api_key"]},
                            json={"session_token": sess["session_token"]}).json()
        assert bal["currency"] == "USD"
        rk = admin.post(f"{API}/admin/providers/{p['id']}/rotate-key").json()
        assert requests.post(f"{API}/provider/v1/balance", headers={"X-Provider-Key": p["api_key"]},
                             json={"session_token": sess["session_token"]}).status_code == 401
        assert requests.post(f"{API}/provider/v1/balance", headers={"X-Provider-Key": rk["api_key"]},
                             json={"session_token": sess["session_token"]}).status_code == 200

    def test_wallet_flow(self, admin):
        p = make_provider(admin)
        H = {"X-Provider-Key": p["api_key"]}
        s, u = make_user()
        admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"amount": 100, "reason": "TEST_fund"})
        tok = s.post(f"{API}/games/launch", json={"provider_id": p["id"]}).json()["session_token"]
        pv = lambda ep, **b: requests.post(f"{API}/provider/v1/{ep}", headers=H, json={"session_token": tok, **b})
        b = pv("bet", transaction_id="b1", round_id="r1", amount=30)
        assert b.status_code == 200 and b.json()["balance"] == 70 and b.json()["currency"] == "USD"
        assert pv("bet", transaction_id="b1", round_id="r1", amount=30).json()["duplicate"] is True
        nf = pv("bet", transaction_id="b2", round_id="r2", amount=500)
        assert nf.status_code == 402
        assert pv("bet", transaction_id="b2", round_id="r2", amount=500).status_code == 402  # retry stays 402
        assert pv("win", transaction_id="w1", round_id="r1", amount=50).json()["balance"] == 120
        pv("bet", transaction_id="b3", round_id="r3", amount=20)
        assert pv("rollback", transaction_id="rb1", ref_transaction_id="b3").json()["balance"] == 120
        nb = pv("win", transaction_id="w3", round_id="r3", amount=10)
        assert nb.status_code == 400 and nb.json()["detail"] == "NO_BET_FOR_ROUND"
        txs = s.get(f"{API}/transactions").json()
        assert txs[0]["balance_after"] == 120 and any(t["reference"] == "r1" for t in txs if t["type"] == "bet")
        assert all(h["status"] == "ok" for h in s.get(f"{API}/games/history").json())


# --- Admin users / support / statement ---
class TestMisc:
    def test_admin_adjust(self, admin):
        s, u = make_user()
        assert admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"amount": 50, "reason": "TEST_b"}).json()["promo_balance"] == 50
        assert admin.post(f"{API}/admin/users/{u['id']}/adjust", json={"amount": -100, "reason": "TEST_o"}).status_code == 400
        assert s.get(f"{API}/wallet").json()["balance"] == 50

    def test_ticket_flow(self, admin):
        s, u = make_user()
        t = s.post(f"{API}/support/tickets", json={"subject": "TEST_ticket", "category": "deposit", "message": "Help me please"}).json()
        ar = admin.post(f"{API}/admin/tickets/{t['id']}/reply", json={"message": "admin reply"}).json()
        assert ar["messages"][-1]["author_role"] == "admin"
        assert admin.patch(f"{API}/admin/tickets/{t['id']}/status", json={"status": "resolved"}).json()["status"] == "resolved"

    def test_no_withdraw(self):
        s, _ = login(*DEMO)
        for p in ["withdraw", "withdrawals"]:
            assert s.post(f"{API}/{p}", json={"amount": 100}).status_code in (404, 405)
