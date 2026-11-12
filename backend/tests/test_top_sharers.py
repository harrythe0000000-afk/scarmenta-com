# Iteration 16: Weekly "Top sharers" leaderboard (calc_share signups) + admin top-3 reward
# Set KEEP_SHARER_DATA=1 to keep created users (ids saved to /tmp/sharer_test_ids.json) for UI testing.
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pymongo
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]

OWNER = ("admin@aetheria.io", "Admin@12345")
STAFF = ("staff@aetheria.io", "Staff@12345")
DEMO = ("demo@aetheria.io", "Demo@12345")
PW = "Test@12345"
S = {"users": [], "sharers": {}}


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


def register(name, ref=None, src=None):
    s = requests.Session()
    email = f"test_sh_{uuid.uuid4().hex[:8]}@example.com"
    body = {"name": name, "email": email, "password": PW, "accepted_terms": True}
    if ref:
        body["referral_code"] = ref
    if src:
        body["signup_source"] = src
    r = s.post(f"{API}/auth/register", json=body)
    assert r.status_code == 200, r.text
    u = r.json()
    S["users"].append(u["id"])
    return s, u


@pytest.fixture(scope="module", autouse=True)
def setup_data():
    assert mdb.sharer_reward_runs.count_documents({}) == 0, "existing reward runs - aborting"
    demo_code = mdb.users.find_one({"email": DEMO[0]})["referral_code"]
    sa, a = register("Devraj Alpha")
    sb, b = register("Bhavesh Bravo")
    sc, c = register("Chandan Charlie")
    sd, d = register("Dinesh Delta")
    S["sharers"] = {"A": a, "B": b, "C": c, "D": d}
    S["sess"] = {"A": sa, "B": sb, "C": sc}
    for _ in range(3):
        register("TEST Friend A", a["referral_code"], "calc_share")
    for _ in range(2):
        register("TEST Friend B", b["referral_code"], "calc_share")
    register("TEST Friend C", c["referral_code"], "calc_share")
    time.sleep(0.05)
    register("TEST Friend Demo", demo_code, "calc_share")  # tie with C, later -> rank 4
    register("TEST Normal Ref", a["referral_code"])  # no src -> not counted
    _, old = register("TEST Old Friend", b["referral_code"], "calc_share")
    mdb.users.update_one({"id": old["id"]}, {"$set": {"created_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()}})
    for _ in range(5):
        register("TEST Friend D", d["referral_code"], "calc_share")
    mdb.users.update_one({"id": d["id"]}, {"$set": {"role": "agent"}})  # non-user referrer excluded
    with open("/tmp/sharer_test_ids.json", "w") as f:
        json.dump({"users": S["users"], "sharers": {k: {"id": v["id"], "email": v["email"]} for k, v in S["sharers"].items()}}, f)
    yield
    if os.environ.get("KEEP_SHARER_DATA") != "1":
        mdb.users.delete_many({"id": {"$in": S["users"]}})
        mdb.transactions.delete_many({"user_id": {"$in": S["users"]}})
        mdb.sharer_reward_runs.delete_many({"winners.user_id": {"$in": S["users"]}})


class TestTopSharers:
    def test_unauth_401(self):
        assert requests.get(f"{API}/leaderboard/sharers").status_code == 401

    def test_ranking_and_masking(self):
        r = S["sess"]["A"].get(f"{API}/leaderboard/sharers")
        assert r.status_code == 200, r.text
        d = r.json()
        assert {"start", "end", "players", "top", "me"} <= d.keys()
        top = d["top"]
        assert [t["friends"] for t in top] == [3, 2, 1, 1], top
        assert [t["rank"] for t in top] == [1, 2, 3, 4]
        assert top[0]["name"] == "De***j" and top[1]["name"] == "Bh***h" and top[2]["name"] == "Ch***n"
        assert top[0]["is_me"] is True and not any(t["is_me"] for t in top[1:])
        assert d["me"] == {"rank": 1, "friends": 3}
        assert d["players"] == 4
        assert all("email" not in t and "user_id" not in t for t in top)

    def test_demo_rank4_tie_break(self):
        d = login(*DEMO).get(f"{API}/leaderboard/sharers").json()
        assert d["me"] == {"rank": 4, "friends": 1}
        assert d["top"][3]["is_me"] is True

    def test_admin_list_full_info(self):
        d = login(*OWNER).get(f"{API}/admin/sharers").json()
        assert d["top"][0]["email"] == S["sharers"]["A"]["email"]
        assert d["top"][0]["name"] == "Devraj Alpha"
        assert S["sharers"]["D"]["id"] not in [t["user_id"] for t in d["top"]]
        assert d["runs"] == []

    def test_staff_forbidden(self):
        s = login(*STAFF)
        assert s.get(f"{API}/admin/sharers").status_code == 403
        assert s.post(f"{API}/admin/sharers/reward", json={"amounts": [1]}).status_code == 403
        assert S["sess"]["A"].get(f"{API}/admin/sharers").status_code == 403

    @pytest.mark.parametrize("amounts,code", [([-1, 5, 5], 400), ([0, 0, 0], 400), ([20000], 400), ([], 422), ([1, 1, 1, 1], 422)])
    def test_amount_validation(self, amounts, code):
        r = login(*OWNER).post(f"{API}/admin/sharers/reward", json={"amounts": amounts})
        assert r.status_code == code, r.text
        assert mdb.sharer_reward_runs.count_documents({}) == 0

    def test_reward_and_once_per_week(self):
        ids = {k: v["id"] for k, v in S["sharers"].items()}
        before = {k: mdb.users.find_one({"id": i})["promo_balance"] for k, i in ids.items()}
        demo_before = mdb.users.find_one({"email": DEMO[0]})["promo_balance"]
        s = login(*OWNER)
        r = s.post(f"{API}/admin/sharers/reward", json={"amounts": [25, 0, 10.555]})
        assert r.status_code == 200, r.text
        run = r.json()
        assert [w["rank"] for w in run["winners"]] == [1, 3]
        assert run["total"] == 35.56 or run["total"] == 35.55
        after = {k: mdb.users.find_one({"id": i})["promo_balance"] for k, i in ids.items()}
        assert round(after["A"] - before["A"], 2) == 25
        assert after["B"] == before["B"]
        assert round(after["C"] - before["C"], 2) in (10.55, 10.56)
        assert mdb.users.find_one({"email": DEMO[0]})["promo_balance"] == demo_before
        tx = mdb.transactions.find_one({"user_id": ids["A"], "type": "sharer_reward"})
        assert tx and tx["amount"] == 25 and tx["wallet"] == "credit" and tx["reference"] == run["id"]
        # visible to player in their transactions
        txs = S["sess"]["A"].get(f"{API}/transactions").json()
        rows = txs if isinstance(txs, list) else txs.get("items", txs.get("transactions", []))
        assert any(t["type"] == "sharer_reward" for t in rows)
        # run listed
        assert s.get(f"{API}/admin/sharers").json()["runs"][0]["id"] == run["id"]
        r2 = s.post(f"{API}/admin/sharers/reward", json={"amounts": [25, 15, 10]})
        assert r2.status_code == 400 and "already rewarded in the last 7 days" in r2.json()["detail"]
