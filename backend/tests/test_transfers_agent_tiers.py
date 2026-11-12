# Iteration 10: Account transfers (5% fee, password proof, lockout, ledger) + agent commission tiers
import os
import time
import uuid

import pymongo
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]

OWNER = ("admin@aetheria.io", "Admin@12345")
STAFF = ("staff@aetheria.io", "Staff@12345")
AGENT = ("agent@aetheria.io", "Agent@12345")
PW = "Test@12345"
C = {"users": [], "deposits": [], "refs": [], "agents": [], "fake": []}


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


def player(balance=0.0, agent_code=None):
    s = requests.Session()
    email = f"test_tr_{uuid.uuid4().hex[:8]}@example.com"
    body = {"name": "TEST Transfer", "email": email, "password": PW}
    if agent_code:
        body["agent_code"] = agent_code
    r = s.post(f"{API}/auth/register", json=body)
    assert r.status_code == 200, r.text
    u = r.json()
    C["users"].append(u["id"])
    mdb.users.update_one({"id": u["id"]}, {"$set": {"email_verified": True, "promo_balance": balance}})
    return s, u


def bal(uid):
    return mdb.users.find_one({"id": uid})["promo_balance"]


@pytest.fixture(scope="module")
def owner():
    return login(*OWNER)


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    ids = C["users"] + C["agents"] + C["fake"]
    mdb.transfers.delete_many({"$or": [{"from_user_id": {"$in": ids}}, {"to_user_id": {"$in": ids}}]})
    mdb.login_attempts.delete_many({"identifier": {"$in": [f"transfer:{i}" for i in ids]}})
    mdb.agent_commissions.delete_many({"agent_id": {"$in": C["agents"]}})
    mdb.deposits.delete_many({"id": {"$in": C["deposits"]}})
    mdb.transactions.delete_many({"user_id": {"$in": ids}})
    mdb.payment_refs.delete_many({"_id": {"$in": C["refs"]}})
    mdb.users.delete_many({"id": {"$in": ids}})


class TestTransfers:
    def test_transfer_success_and_ledger(self):
        s, a = player(500.0)
        _, b = player(0.0)
        r = s.post(f"{API}/transfers", json={"to_email": b["email"], "to_password": PW, "amount": 100})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["fee_percent"] == 5 and d["fee"] == 5.0 and d["net"] == 95.0 and d["reference"].startswith("TRF-")
        assert "_id" not in d
        assert bal(a["id"]) == 400.0 and bal(b["id"]) == 95.0
        h = s.get(f"{API}/transfers").json()
        assert h[0]["reference"] == d["reference"]
        tx = s.get(f"{API}/transactions").json() if s.get(f"{API}/transactions").status_code == 200 else None
        types = {t["type"] for t in mdb.transactions.find({"reference": d["reference"]})}
        assert types == {"transfer_out", "transfer_in"}
        # receiver sees it in history
        rs = login(b["email"], PW)
        assert any(t["reference"] == d["reference"] for t in rs.get(f"{API}/transfers").json())
        assert rs.get(f"{API}/wallet").json()["balance"] == 95.0

    def test_validation_errors(self):
        s, a = player(50.0)
        _, b = player(0.0)
        assert s.post(f"{API}/transfers", json={"to_email": a["email"], "to_password": PW, "amount": 10}).status_code == 400
        r = s.post(f"{API}/transfers", json={"to_email": b["email"], "to_password": PW, "amount": 100})
        assert r.status_code == 400 and "Insufficient" in r.json()["detail"]
        for em in ["admin@aetheria.io", "staff@aetheria.io", "agent@aetheria.io"]:
            assert s.post(f"{API}/transfers", json={"to_email": em, "to_password": "x", "amount": 10}).status_code == 400
        assert s.post(f"{API}/transfers", json={"to_email": b["email"], "to_password": PW, "amount": 0}).status_code == 422
        assert s.post(f"{API}/transfers", json={"to_email": b["email"], "to_password": PW, "amount": -5}).status_code == 422
        assert bal(a["id"]) == 50.0 and bal(b["id"]) == 0.0

    def test_wrong_password_lockout(self):
        s, a = player(50.0)
        _, b = player(0.0)
        codes = [s.post(f"{API}/transfers", json={"to_email": b["email"], "to_password": "Wrong@123", "amount": 10}).status_code
                 for _ in range(5)]
        assert codes == [401, 401, 401, 401, 429], codes
        # locked even with the right password
        assert s.post(f"{API}/transfers", json={"to_email": b["email"], "to_password": PW, "amount": 10}).status_code == 429
        assert bal(a["id"]) == 50.0

    def test_fee_config_change(self, owner):
        st = owner.get(f"{API}/admin/settings").json()
        orig = st["transfer_fee_percent"]
        body = {k: v for k, v in st.items() if k not in ("_id", "id", "updated_at", "updated_by")}
        try:
            body["transfer_fee_percent"] = 10
            r = owner.put(f"{API}/admin/settings", json=body)
            assert r.status_code == 200, r.text
            assert requests.get(f"{API}/public/config").json()["transfer_fee_percent"] == 10
            s, a = player(200.0)
            _, b = player(0.0)
            d = s.post(f"{API}/transfers", json={"to_email": b["email"], "to_password": PW, "amount": 100}).json()
            assert d["fee"] == 10.0 and d["net"] == 90.0
            body["transfer_fee_percent"] = 51
            assert owner.put(f"{API}/admin/settings", json=body).status_code == 422
        finally:
            body["transfer_fee_percent"] = orig
            assert owner.put(f"{API}/admin/settings", json=body).status_code == 200
        assert requests.get(f"{API}/public/config").json()["transfer_fee_percent"] == orig

    def test_admin_transfers_access(self, owner):
        assert owner.get(f"{API}/admin/transfers").status_code == 200
        assert login(*STAFF).get(f"{API}/admin/transfers").status_code == 200
        s, _ = player(0)
        assert s.get(f"{API}/admin/transfers").status_code == 403
        # non-player can't transfer
        r = login(*STAFF).post(f"{API}/transfers", json={"to_email": "demo@aetheria.io", "to_password": "x", "amount": 1})
        assert r.status_code == 403


class TestAgentTiers:
    def _deposit_approve(self, owner, sess, amount=100.0):
        ref = "TESTREF" + uuid.uuid4().hex[:10].upper()
        r = sess.post(f"{API}/deposits", json={"amount": amount, "method": "usdt", "network": "TRC20", "payment_reference": ref})
        assert r.status_code == 200, r.text
        C["deposits"].append(r.json()["id"])
        C["refs"].append(ref.upper())
        assert owner.post(f"{API}/admin/deposits/{r.json()['id']}/approve").status_code == 200
        time.sleep(0.5)
        return mdb.agent_commissions.find_one({"deposit_ref": r.json()["reference"]})

    def _fake(self, agent_id, n):
        docs = [{"id": "TESTFAKE-" + uuid.uuid4().hex, "email": f"test_fake_{uuid.uuid4().hex[:8]}@example.com",
                 "name": "TEST Fake", "role": "user", "status": "active", "agent_id": agent_id, "promo_balance": 0.0,
                 "created_at": "2026-01-01T00:00:00+00:00"} for _ in range(n)]
        mdb.users.insert_many(docs)
        C["fake"].extend(d["id"] for d in docs)

    def test_tiers(self, owner):
        r = owner.post(f"{API}/admin/agents", json={"name": "TEST Tier Agent", "email": f"test_tier_{uuid.uuid4().hex[:6]}@example.com",
                                                   "password": "Agent@1234"})
        assert r.status_code == 200, r.text
        ag = r.json()
        C["agents"].append(ag["id"])
        assert ag.get("commission_percent") is None
        sess, _ = player(0, agent_code=ag["agent_code"])
        c = self._deposit_approve(owner, sess)
        assert c and c["percent"] == 5.0 and c["amount"] == 5.0
        row = next(a for a in owner.get(f"{API}/admin/agents").json() if a["id"] == ag["id"])
        assert row["current_rate"] == 5.0 and row["players"] == 1
        self._fake(ag["id"], 10)  # 11 players
        c = self._deposit_approve(owner, sess)
        assert c["percent"] == 7.0 and c["amount"] == 7.0
        row = next(a for a in owner.get(f"{API}/admin/agents").json() if a["id"] == ag["id"])
        assert row["current_rate"] == 7.0
        self._fake(ag["id"], 40)  # 51 players
        c = self._deposit_approve(owner, sess)
        assert c["percent"] == 10.0 and c["amount"] == 10.0
        me = login(ag["email"], "Agent@1234").get(f"{API}/agent/me").json()
        assert me["commission_percent"] == 10.0 and "51+" in me["tiers"]

    def test_seed_agent_rate(self, owner):
        me = login(*AGENT).get(f"{API}/agent/me").json()
        assert me["commission_percent"] == (5.0 if len(me["players_list"]) <= 10 else 7.0)
