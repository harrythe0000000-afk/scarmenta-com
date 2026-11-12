# Staff admin role (RBAC) + owner staff management + staff deposit review tests
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
mdb = MongoClient("mongodb://localhost:27017")["test_database"]
OWNER = ("admin@aetheria.io", "Admin@12345")
STAFF = ("staff@aetheria.io", "Staff@12345")
DEMO = ("demo@aetheria.io", "Demo@12345")


def login(email, pwd):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text
    return s, r.json()


@pytest.fixture(scope="module")
def owner():
    return login(*OWNER)[0]


@pytest.fixture(scope="module")
def staff():
    return login(*STAFF)[0]


@pytest.fixture(scope="module")
def player():
    return login(*DEMO)[0]


@pytest.fixture(scope="module")
def cleanup():
    data = {"users": [], "tickets": [], "deposits": []}
    yield data
    for uid in data["users"]:
        mdb.users.delete_one({"id": uid, "email": {"$regex": "^test_staff_"}})
    for tid in data["tickets"]:
        mdb.tickets.delete_one({"id": tid})


OWNER_ONLY = [("get", "/api/admin/settings", None), ("put", "/api/admin/settings", {}),
              ("get", "/api/admin/providers", None), ("post", "/api/admin/providers", {}),
              ("post", "/api/admin/providers/x/rotate-key", None), ("put", "/api/admin/providers/x", {}),
              ("get", "/api/admin/staff", None), ("post", "/api/admin/staff", {}),
              ("patch", "/api/admin/staff/x/status", {"status": "active"}),
              ("get", "/api/admin/loss-rewards/preview", None), ("get", "/api/admin/loss-rewards/runs", None),
              ("post", "/api/admin/loss-rewards/run", {}),
              ("patch", "/api/admin/users/x/status", {"status": "active"}),
              ("post", "/api/admin/users/x/adjust", {"amount": 1, "reason": "abc"})]
STAFF_OK = ["/api/admin/stats", "/api/admin/users", "/api/admin/deposits", "/api/admin/transactions",
            "/api/admin/fraud", "/api/admin/tickets", "/api/admin/referrals", "/api/admin/money-flow",
            "/api/admin/game-stats", "/api/admin/game-transactions"]


# Staff login
def test_staff_login_role():
    s, u = login(*STAFF)
    assert u["role"] == "staff" and u["email"] == STAFF[0]
    assert "password_hash" not in u
    assert s.get(f"{BASE_URL}/api/auth/me").json()["role"] == "staff"


# Staff blocked from owner-only endpoints
@pytest.mark.parametrize("method,path,body", OWNER_ONLY)
def test_staff_403_owner_only(staff, method, path, body):
    r = getattr(staff, method)(f"{BASE_URL}{path}", json=body) if body is not None else getattr(staff, method)(f"{BASE_URL}{path}")
    assert r.status_code == 403, f"{method} {path} -> {r.status_code} {r.text}"


# Staff allowed on staff endpoints
@pytest.mark.parametrize("path", STAFF_OK)
def test_staff_allowed(staff, path):
    r = staff.get(f"{BASE_URL}{path}")
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text}"


# Players blocked on all admin endpoints
@pytest.mark.parametrize("path", STAFF_OK + [p for m, p, b in OWNER_ONLY if m == "get"])
def test_player_403_admin(player, path):
    r = player.get(f"{BASE_URL}{path}")
    assert r.status_code == 403, f"{path} -> {r.status_code}"


def test_player_403_admin_writes(player):
    for path in ["/api/admin/deposits/x/approve", "/api/admin/fraud/x/resolve", "/api/admin/staff"]:
        r = player.post(f"{BASE_URL}{path}", json={"name": "TEST_x", "email": "test_staff_x@example.com", "password": "Abcdefgh1"})
        assert r.status_code == 403, f"{path} -> {r.status_code}"


# Owner sees settings/staff list incl. owner + staff
def test_owner_staff_list(owner):
    r = owner.get(f"{BASE_URL}/api/admin/staff")
    assert r.status_code == 200
    roles = {u["email"]: u["role"] for u in r.json()}
    assert roles.get(OWNER[0]) == "admin" and roles.get(STAFF[0]) == "staff"
    assert all("password_hash" not in u for u in r.json())
    assert owner.get(f"{BASE_URL}/api/admin/settings").status_code == 200


# Owner creates staff, duplicate, disable -> 403 login, enable -> ok
def test_staff_lifecycle(owner, cleanup):
    email = f"test_staff_{uuid.uuid4().hex[:8]}@example.com"
    r = owner.post(f"{BASE_URL}/api/admin/staff", json={"name": "TEST_Staff", "email": email, "password": "Temp@12345"})
    assert r.status_code == 200, r.text
    st = r.json(); cleanup["users"].append(st["id"])
    assert st["role"] == "staff" and st["status"] == "active" and st["email"] == email and "password_hash" not in st
    dup = owner.post(f"{BASE_URL}/api/admin/staff", json={"name": "TEST_Dup", "email": email.upper(), "password": "Temp@12345"})
    assert dup.status_code == 400
    dup2 = owner.post(f"{BASE_URL}/api/admin/staff", json={"name": "TEST_Dup", "email": DEMO[0], "password": "Temp@12345"})
    assert dup2.status_code == 400
    blank = owner.post(f"{BASE_URL}/api/admin/staff", json={"name": "   ", "email": "test_staff_b@example.com", "password": "Temp@12345"})
    assert blank.status_code == 422
    short = owner.post(f"{BASE_URL}/api/admin/staff", json={"name": "TEST_S", "email": "test_staff_c@example.com", "password": "short"})
    assert short.status_code == 422
    s2, _ = login(email, "Temp@12345")
    assert owner.patch(f"{BASE_URL}/api/admin/staff/{st['id']}/status", json={"status": "suspended"}).status_code == 200
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": "Temp@12345"})
    assert r.status_code == 403
    # existing session also blocked
    assert s2.get(f"{BASE_URL}/api/admin/deposits").status_code == 403
    assert owner.patch(f"{BASE_URL}/api/admin/staff/{st['id']}/status", json={"status": "active"}).status_code == 200
    login(email, "Temp@12345")


def test_owner_cannot_disable_owner_via_staff_endpoint(owner):
    oid = mdb.users.find_one({"email": OWNER[0]})["id"]
    assert owner.patch(f"{BASE_URL}/api/admin/staff/{oid}/status", json={"status": "suspended"}).status_code == 404


# Staff approve/reject deposit -> reviewed_by staff email
def test_staff_review_deposits(player, staff, cleanup):
    before = player.get(f"{BASE_URL}/api/wallet").json()["balance"]
    refs = []
    for _ in range(2):
        r = player.post(f"{BASE_URL}/api/deposits", json={"amount": 10, "method": "usdt", "network": "TRC20",
                                                          "payment_reference": f"TEST_{uuid.uuid4().hex[:10]}"})
        assert r.status_code == 200, r.text
        refs.append(r.json())
    a = staff.post(f"{BASE_URL}/api/admin/deposits/{refs[0]['id']}/approve")
    assert a.status_code == 200, a.text
    assert a.json()["status"] == "approved" and a.json()["reviewed_by"] == STAFF[0]
    after = player.get(f"{BASE_URL}/api/wallet").json()["balance"]
    assert round(after - before, 2) == round(refs[0]["promo_credit"], 2)
    j = staff.post(f"{BASE_URL}/api/admin/deposits/{refs[1]['id']}/reject", json={"reason": "TEST reject"})
    assert j.status_code == 200 and j.json()["reviewed_by"] == STAFF[0] and j.json()["status"] == "rejected"
    assert staff.post(f"{BASE_URL}/api/admin/deposits/{refs[0]['id']}/approve").status_code == 409
    # resolve fraud alerts created by these deposits (velocity)
    alerts = list(mdb.fraud_alerts.find({"reference": {"$in": [d["reference"] for d in refs]}, "status": "open"}))
    for al in alerts:
        r = staff.post(f"{BASE_URL}/api/admin/fraud/{al['id']}/resolve")
        assert r.status_code == 200
        assert mdb.fraud_alerts.find_one({"id": al["id"]})["resolved_by"] == STAFF[0]


# Staff replies to a ticket
def test_staff_ticket_reply(player, staff, cleanup):
    t = player.post(f"{BASE_URL}/api/support/tickets", json={"subject": "TEST_ticket", "category": "other", "message": "TEST hello"})
    assert t.status_code == 200
    tid = t.json()["id"]; cleanup["tickets"].append(tid)
    r = staff.post(f"{BASE_URL}/api/admin/tickets/{tid}/reply", json={"message": "TEST staff reply"})
    assert r.status_code == 200
    assert r.json()["messages"][-1]["author_role"] == "staff"
    s = staff.patch(f"{BASE_URL}/api/admin/tickets/{tid}/status", json={"status": "resolved"})
    assert s.status_code == 200 and s.json()["status"] == "resolved"


# Staff can update own account (name) and restore
def test_staff_account_update(staff):
    r = staff.put(f"{BASE_URL}/api/auth/account", json={"current_password": STAFF[1], "name": "TEST_StaffName"})
    assert r.status_code == 200 and r.json()["name"] == "TEST_StaffName"
    orig = "Staff Tester"
    r = staff.put(f"{BASE_URL}/api/auth/account", json={"current_password": STAFF[1], "name": orig})
    assert r.status_code == 200
