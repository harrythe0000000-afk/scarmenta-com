# Iteration 9: Agent accounts (owner CRUD, staff read-only, agent portal, commission on approval) + deposit alerts toggle
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
DEMO = ("demo@aetheria.io", "Demo@12345")

CREATED = {"users": [], "deposits": [], "refs": [], "agents": []}


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


def uniq_ref():
    return "TESTREF" + uuid.uuid4().hex[:10].upper()


@pytest.fixture(scope="module")
def owner():
    return login(*OWNER)


@pytest.fixture(scope="module")
def staff():
    return login(*STAFF)


@pytest.fixture(scope="module")
def agent():
    return login(*AGENT)


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    ids = CREATED["users"] + CREATED["agents"]
    mdb.agent_commissions.delete_many({"agent_id": {"$in": CREATED["agents"]}})
    mdb.agent_payouts.delete_many({"agent_id": {"$in": CREATED["agents"]}})
    mdb.deposits.delete_many({"id": {"$in": CREATED["deposits"]}})
    mdb.transactions.delete_many({"user_id": {"$in": CREATED["users"]}})
    mdb.payment_refs.delete_many({"_id": {"$in": CREATED["refs"]}})
    mdb.users.delete_many({"id": {"$in": ids}})


def new_player(agent_code):
    s = requests.Session()
    email = f"test_ap_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"name": "TEST Agent Player", "email": email, "password": "Test@12345",
                                             "agent_code": agent_code})
    assert r.status_code == 200, r.text
    u = r.json()
    CREATED["users"].append(u["id"])
    mdb.users.update_one({"id": u["id"]}, {"$set": {"email_verified": True}})
    return s, u


def deposit(sess, amount=100.0):
    ref = uniq_ref()
    t = time.time()
    r = sess.post(f"{API}/deposits", json={"amount": amount, "method": "usdt", "network": "TRC20", "payment_reference": ref})
    elapsed = time.time() - t
    assert r.status_code == 200, r.text
    CREATED["deposits"].append(r.json()["id"])
    CREATED["refs"].append(ref.upper())
    return r.json(), elapsed


class TestAgentsFlow:
    state = {}

    def test_staff_read_only(self, staff):
        assert staff.get(f"{API}/admin/agents").status_code == 200
        assert staff.post(f"{API}/admin/agents", json={"name": "TEST X", "email": "test_x@example.com",
                                                       "password": "Test@12345", "commission_percent": 5}).status_code == 403
        aid = mdb.users.find_one({"email": AGENT[0]})["id"]
        assert staff.patch(f"{API}/admin/agents/{aid}", json={"commission_percent": 7}).status_code == 403
        assert staff.post(f"{API}/admin/agents/{aid}/payout", json={}).status_code == 403

    def test_agent_forbidden_on_admin_and_deposit(self, agent):
        for p in ["/admin/stats", "/admin/agents", "/admin/deposits", "/admin/users", "/admin/settings"]:
            assert agent.get(f"{API}{p}").status_code == 403, p
        r = agent.post(f"{API}/deposits", json={"amount": 100, "method": "usdt", "network": "TRC20", "payment_reference": uniq_ref()})
        assert r.status_code == 403

    def test_agent_me(self, agent):
        r = agent.get(f"{API}/agent/me")
        assert r.status_code == 200
        d = r.json()
        for k in ["name", "code", "commission_percent", "link", "players", "volume", "earned", "unpaid", "paid",
                  "players_list", "commissions", "payouts"]:
            assert k in d
        assert d["link"].endswith(f"/register?agent={d['code']}")
        assert "player_id" not in str(d["commissions"])

    def test_non_agent_on_agent_me(self, owner):
        assert owner.get(f"{API}/agent/me").status_code == 403

    def test_create_agent_and_duplicate(self, owner):
        email = f"test_agent_{uuid.uuid4().hex[:6]}@example.com"
        r = owner.post(f"{API}/admin/agents", json={"name": "TEST Agent", "email": email, "password": "Test@12345",
                                                    "commission_percent": 10})
        assert r.status_code == 200, r.text
        a = r.json()
        CREATED["agents"].append(a["id"])
        assert a["agent_code"].startswith("AG") and a["role"] == "agent" and a["commission_percent"] == 10
        assert "password_hash" not in a and "_id" not in a
        self.state.update(agent=a, email=email)
        dup = owner.post(f"{API}/admin/agents", json={"name": "TEST Agent", "email": email.upper(), "password": "Test@12345",
                                                      "commission_percent": 10})
        assert dup.status_code == 400
        bad = owner.post(f"{API}/admin/agents", json={"name": "TEST", "email": "test_b@example.com", "password": "Test@12345",
                                                      "commission_percent": 60})
        assert bad.status_code == 422
        lst = owner.get(f"{API}/admin/agents").json()
        row = next(x for x in lst if x["id"] == a["id"])
        assert row["players"] == 0 and row["unpaid"] == 0

    def test_new_agent_can_login(self):
        s = login(self.state["email"], "Test@12345")
        assert s.get(f"{API}/auth/me").json()["role"] == "agent"

    def test_invalid_agent_code(self):
        r = requests.post(f"{API}/auth/register", json={"name": "TEST bad", "email": f"test_bad_{uuid.uuid4().hex[:6]}@example.com",
                                                        "password": "Test@12345", "agent_code": "AGNOPE00"})
        assert r.status_code == 400 and "Invalid agent code" in r.text

    def test_register_with_code_lowercase_links(self):
        s, u = new_player(self.state["agent"]["agent_code"].lower())
        assert mdb.users.find_one({"id": u["id"]})["agent_id"] == self.state["agent"]["id"]
        self.state.update(player=s, player_id=u["id"])

    def test_deposit_fast_and_approve_commission(self, owner, staff):
        dep, elapsed = deposit(self.state["player"], 150.0)
        assert elapsed < 3, f"deposit took {elapsed:.2f}s"
        r = staff.post(f"{API}/admin/deposits/{dep['id']}/approve")
        assert r.status_code == 200
        rows = list(mdb.agent_commissions.find({"deposit_ref": dep["reference"]}))
        assert len(rows) == 1 and rows[0]["amount"] == 15.0 and rows[0]["status"] == "unpaid"
        again = owner.post(f"{API}/admin/deposits/{dep['id']}/approve")
        assert again.status_code == 409
        assert mdb.agent_commissions.count_documents({"deposit_ref": dep["reference"]}) == 1
        row = next(x for x in owner.get(f"{API}/admin/agents").json() if x["id"] == self.state["agent"]["id"])
        assert row["players"] == 1 and row["volume"] == 150.0 and row["earned"] == 15.0 and row["unpaid"] == 15.0

    def test_update_rate(self, owner):
        aid = self.state["agent"]["id"]
        r = owner.patch(f"{API}/admin/agents/{aid}", json={"commission_percent": 20})
        assert r.status_code == 200 and r.json()["commission_percent"] == 20 and "password_hash" not in r.json()
        assert owner.patch(f"{API}/admin/agents/{aid}", json={}).status_code == 400
        assert owner.patch(f"{API}/admin/agents/nonexistent", json={"commission_percent": 5}).status_code == 404

    def test_payout(self, owner):
        aid = self.state["agent"]["id"]
        r = owner.post(f"{API}/admin/agents/{aid}/payout", json={"note": "TEST tx"})
        assert r.status_code == 200 and r.json()["amount"] == 15.0 and r.json()["count"] == 1
        row = next(x for x in owner.get(f"{API}/admin/agents").json() if x["id"] == aid)
        assert row["unpaid"] == 0 and row["paid"] == 15.0
        assert owner.post(f"{API}/admin/agents/{aid}/payout", json={}).status_code == 400
        s = login(self.state["email"], "Test@12345")
        me = s.get(f"{API}/agent/me").json()
        assert me["paid"] == 15.0 and len(me["payouts"]) == 1 and me["players_list"][0]["deposited"] == 150.0

    def test_disabled_agent_no_commission(self, owner):
        aid = self.state["agent"]["id"]
        assert owner.patch(f"{API}/admin/agents/{aid}", json={"status": "suspended"}).json()["status"] == "suspended"
        dep, _ = deposit(self.state["player"], 100.0)
        assert owner.post(f"{API}/admin/deposits/{dep['id']}/approve").status_code == 200
        assert mdb.agent_commissions.count_documents({"deposit_ref": dep["reference"]}) == 0
        r = requests.post(f"{API}/auth/login", json={"email": self.state["email"], "password": "Test@12345"})
        assert r.status_code in (401, 403)
        reg = requests.post(f"{API}/auth/register", json={"name": "TEST d", "email": f"test_d_{uuid.uuid4().hex[:6]}@example.com",
                                                          "password": "Test@12345", "agent_code": self.state["agent"]["agent_code"]})
        assert reg.status_code == 400
        assert owner.patch(f"{API}/admin/agents/{aid}", json={"status": "active"}).json()["status"] == "active"


class TestDepositAlertsSettings:
    def test_settings_require_deposit_alerts(self, owner):
        s = owner.get(f"{API}/admin/settings").json()
        assert "deposit_alerts" in s
        body = {k: v for k, v in s.items() if k != "deposit_alerts"}
        assert owner.put(f"{API}/admin/settings", json=body).status_code == 422

    def test_toggle_and_restore(self, owner):
        s = owner.get(f"{API}/admin/settings").json()
        orig = s["deposit_alerts"]
        r = owner.put(f"{API}/admin/settings", json={**s, "deposit_alerts": not orig})
        assert r.status_code == 200, r.text
        assert owner.get(f"{API}/admin/settings").json()["deposit_alerts"] == (not orig)
        assert owner.put(f"{API}/admin/settings", json={**s, "deposit_alerts": orig}).status_code == 200
        assert owner.get(f"{API}/admin/settings").json()["deposit_alerts"] == orig

    def test_demo_deposit_fast(self, owner):
        d = login(*DEMO)
        dep, elapsed = deposit(d, 100.0)
        assert elapsed < 3, f"{elapsed:.2f}s"
        # reject to restore demo state (frees the reference)
        assert owner.post(f"{API}/admin/deposits/{dep['id']}/reject", json={"reason": "TEST cleanup"}).status_code == 200
