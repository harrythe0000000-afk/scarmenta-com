# Instant bot answers (CRUD + RBAC + LLM usage), chat ratings, insights ratings, share visit/stats/bonus tests
import json
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
DEMO = ("demo@aetheria.io", "Demo@12345")
ADMIN = ("admin@aetheria.io", "Admin@12345")
STAFF = ("staff@aetheria.io", "Staff@12345")
AGENT = ("agent@aetheria.io", "Agent@12345")


def _mongo():
    env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l and not l.startswith("#"))
    return MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]


DB = _mongo()
C = {"answers": [], "users": [], "deposits": [], "sessions": []}


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    return s


def chat(s, sid, msg):
    r = s.post(f"{API}/assistant/chat", json={"session_id": sid, "message": msg}, stream=True, timeout=120)
    assert r.status_code == 200, r.text
    text, mid = "", None
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        p = line[6:]
        if p == "[DONE]":
            break
        ev = json.loads(p)
        assert "error" not in ev, ev
        text += ev.get("delta", "")
        mid = ev.get("message_id", mid)
    return text, mid


@pytest.fixture(scope="module")
def admin():
    return login(*ADMIN)


@pytest.fixture(scope="module")
def staff():
    return login(*STAFF)


@pytest.fixture(scope="module")
def demo():
    return login(*DEMO)


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    DB.bot_answers.delete_many({"id": {"$in": C["answers"]}})
    if C["users"]:
        DB.transactions.delete_many({"user_id": {"$in": C["users"]}})
        DB.share_visits.delete_many({"referrer_id": {"$in": C["users"]}})
        DB.users.delete_many({"id": {"$in": C["users"]}})
    DB.deposits.delete_many({"id": {"$in": C["deposits"]}})
    DB.chat_messages.delete_many({"session_id": {"$in": C["sessions"]}})


# ---------- Bot answers CRUD + RBAC ----------
class TestBotAnswers:
    def test_crud_and_rbac(self, admin, staff, demo):
        r = admin.post(f"{API}/admin/assistant/answers", json={"question": "TEST_What is foo?", "answer": "TEST_Foo is bar."})
        assert r.status_code == 200, r.text
        a = r.json()
        C["answers"].append(a["id"])
        assert a["active"] is True and a["question"] == "TEST_What is foo?"
        # staff can list
        r = staff.get(f"{API}/admin/assistant/answers")
        assert r.status_code == 200 and any(x["id"] == a["id"] for x in r.json())
        # player cannot list
        assert demo.get(f"{API}/admin/assistant/answers").status_code == 403
        # staff/player cannot write
        for s in (staff, demo):
            assert s.post(f"{API}/admin/assistant/answers", json={"question": "xxx?", "answer": "yyy"}).status_code == 403
            assert s.patch(f"{API}/admin/assistant/answers/{a['id']}", json={"active": False}).status_code == 403
            assert s.delete(f"{API}/admin/assistant/answers/{a['id']}").status_code == 403
        # edit + toggle
        assert admin.patch(f"{API}/admin/assistant/answers/{a['id']}", json={"answer": "TEST_Foo is baz.", "active": False}).status_code == 200
        row = next(x for x in admin.get(f"{API}/admin/assistant/answers").json() if x["id"] == a["id"])
        assert row["answer"] == "TEST_Foo is baz." and row["active"] is False
        assert admin.patch(f"{API}/admin/assistant/answers/{a['id']}", json={}).status_code == 400
        assert admin.patch(f"{API}/admin/assistant/answers/nope", json={"active": True}).status_code == 404
        assert admin.post(f"{API}/admin/assistant/answers", json={"question": "ab", "answer": "x"}).status_code == 422
        # delete
        assert admin.delete(f"{API}/admin/assistant/answers/{a['id']}").status_code == 200
        assert not any(x["id"] == a["id"] for x in admin.get(f"{API}/admin/assistant/answers").json())
        assert admin.patch(f"{API}/admin/assistant/answers/{a['id']}", json={"active": True}).status_code == 404


# ---------- Official answer used by LLM + rating ----------
class TestOfficialAnswerAndRating:
    def test_official_answer_hinglish_then_rate(self, admin, demo, staff):
        r = admin.post(f"{API}/admin/assistant/answers", json={
            "question": "What are support hours?",
            "answer": "Support is available 10 AM to 8 PM IST, Monday to Saturday."})
        aid = r.json()["id"]
        C["answers"].append(aid)
        sid = f"test-{uuid.uuid4().hex[:16]}"
        C["sessions"].append(sid)
        text, mid = chat(demo, sid, "support kab available hai?")
        print("ON reply:", text)
        low = text.lower().replace(" ", "")
        assert "10" in low and "8" in low and "ist" in low, text
        assert mid
        # rating up
        assert demo.post(f"{API}/assistant/messages/{mid}/rate", json={"rating": "up"}).status_code == 200
        h = demo.get(f"{API}/assistant/history", params={"session_id": sid}).json()
        bot = [m for m in h if m["role"] == "assistant"][-1]
        assert bot["id"] == mid and bot["rating"] == "up"
        # down with reason
        assert demo.post(f"{API}/assistant/messages/{mid}/rate", json={"rating": "down", "reason": "TEST_reason too vague"}).status_code == 200
        h = demo.get(f"{API}/assistant/history", params={"session_id": sid}).json()
        assert [m for m in h if m["role"] == "assistant"][-1]["rating"] == "down"
        # invalid rating
        assert demo.post(f"{API}/assistant/messages/{mid}/rate", json={"rating": "meh"}).status_code == 422
        # other user's message -> 404
        agent = login(*AGENT)
        assert agent.post(f"{API}/assistant/messages/{mid}/rate", json={"rating": "up"}).status_code == 404
        assert demo.post(f"{API}/assistant/messages/doesnotexist/rate", json={"rating": "up"}).status_code == 404
        # insights
        ins = staff.get(f"{API}/admin/assistant/insights", params={"days": 7}).json()
        assert ins["ratings"]["down"] >= 1
        row = next((d for d in ins["disliked"] if d["reason"] == "TEST_reason too vague"), None)
        assert row and row["question"] == "support kab available hai?" and row["name"]

        # toggle off -> answer not forced
        admin.patch(f"{API}/admin/assistant/answers/{aid}", json={"active": False})
        sid2 = f"test-{uuid.uuid4().hex[:16]}"
        C["sessions"].append(sid2)
        text2, _ = chat(demo, sid2, "support kab available hai?")
        print("OFF reply:", text2)
        assert not ("10 am" in text2.lower() and "8 pm" in text2.lower()), text2


# ---------- Share visits / stats / bonus ----------
def register(code, src):
    s = requests.Session()
    email = f"test_share_{uuid.uuid4().hex[:8]}@example.com"
    body = {"name": "TEST Share Friend", "email": email, "password": "Test@12345", "referral_code": code,
            "accepted_terms": True, "terms_version": "1"}
    if src:
        body["signup_source"] = src
    r = s.post(f"{API}/auth/register", json=body)
    assert r.status_code == 200, r.text
    u = DB.users.find_one({"email": email}, {"_id": 0})
    C["users"].append(u["id"])
    DB.users.update_one({"id": u["id"]}, {"$set": {"email_verified": True}})
    return s, u


def deposit(s, admin, amount=50):
    r = s.post(f"{API}/deposits", json={"amount": amount, "method": "usdt", "network": "TRC20",
                                        "payment_reference": f"TESTREF{uuid.uuid4().hex[:10]}"})
    assert r.status_code == 200, r.text
    C["deposits"].append(r.json()["id"])
    assert admin.post(f"{API}/admin/deposits/{r.json()['id']}/approve").status_code == 200


class TestShare:
    def test_share_flow(self, admin):
        # sharer: fresh TEST user
        sharer_s, sharer = register(None, None)
        code = sharer["referral_code"]
        assert code
        st0 = sharer_s.get(f"{API}/share/me").json()
        assert st0 == {"bonus_amount": st0["bonus_amount"], "visits": 0, "signups": 0, "deposited": 0, "earned": 0}
        assert requests.post(f"{API}/share/visit", json={"code": code}).status_code == 200
        assert requests.post(f"{API}/share/visit", json={"code": "ZZZZNOPE"}).status_code == 200
        assert sharer_s.get(f"{API}/share/me").json()["visits"] == 1

        settings = admin.get(f"{API}/admin/settings").json()
        assert settings.get("share_bonus_amount") == 5 or settings.get("share_bonus_amount") is not None
        bonus = settings["share_bonus_amount"]
        assert bonus > 0

        # friend via share link
        fs, friend = register(code, "calc_share")
        assert friend["signup_source"] == "calc_share" and friend["referred_by"] == sharer["id"]
        before = DB.users.find_one({"id": sharer["id"]})["promo_balance"]
        deposit(fs, admin, 50)
        after = DB.users.find_one({"id": sharer["id"]})
        ref_pct = settings["referral_bonus_percent"]
        assert round(after["promo_balance"] - before, 2) == round(bonus + 50 * ref_pct / 100, 2)
        txs = list(DB.transactions.find({"user_id": sharer["id"], "type": "share_bonus"}))
        assert len(txs) == 1 and txs[0]["amount"] == bonus
        # second deposit -> no extra share bonus
        deposit(fs, admin, 50)
        assert DB.transactions.count_documents({"user_id": sharer["id"], "type": "share_bonus"}) == 1
        st = sharer_s.get(f"{API}/share/me").json()
        assert st["signups"] == 1 and st["deposited"] == 1 and st["earned"] == bonus

        # normal ref link -> no share bonus
        ns, normal = register(code, None)
        assert normal.get("signup_source") is None
        deposit(ns, admin, 50)
        assert DB.transactions.count_documents({"user_id": sharer["id"], "type": "share_bonus"}) == 1
        # statement shows share_bonus
        stm = sharer_s.get(f"{API}/transactions")
        if stm.status_code == 200:
            data = stm.json()
            items = data if isinstance(data, list) else data.get("items", [])
            assert any(t["type"] == "share_bonus" for t in items)

        # bonus disabled (0) -> no bonus; then restore
        settings_put = {k: settings[k] for k in settings if k not in ("_id", "id", "updated_at", "updated_by")}
        try:
            settings_put["share_bonus_amount"] = 0
            r = admin.put(f"{API}/admin/settings", json=settings_put)
            assert r.status_code == 200, r.text
            s2 = admin.get(f"{API}/admin/settings").json()
            assert s2["share_bonus_amount"] == 0 and s2["promo_multiplier"] == settings["promo_multiplier"]
            assert s2["packages"] == settings["packages"]
            zs, z = register(code, "calc_share")
            deposit(zs, admin, 50)
            assert DB.transactions.count_documents({"user_id": sharer["id"], "type": "share_bonus"}) == 1
            assert sharer_s.get(f"{API}/share/me").json()["bonus_amount"] == 0
        finally:
            settings_put["share_bonus_amount"] = bonus
            assert admin.put(f"{API}/admin/settings", json=settings_put).status_code == 200

    def test_signup_source_without_ref_is_dropped(self):
        s, u = register(None, "calc_share")
        assert u.get("signup_source") is None
