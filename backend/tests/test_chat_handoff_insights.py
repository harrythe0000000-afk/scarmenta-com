# Chat handoff (auto ticket), agent chat access, rate limit and admin chat insights tests
import json
import os
import uuid
from datetime import datetime, timezone

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


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    return s


def chat(s, sid, msg):
    r = s.post(f"{API}/assistant/chat", json={"session_id": sid, "message": msg}, stream=True, timeout=120)
    assert r.status_code == 200, r.text
    text, events, done = "", [], False
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        p = line[6:]
        if p == "[DONE]":
            done = True
            break
        ev = json.loads(p)
        events.append(ev)
        assert "error" not in ev, ev
        text += ev.get("delta", "")
    assert done
    return text, events


@pytest.fixture(scope="module")
def demo():
    return login(*DEMO)


@pytest.fixture(scope="module")
def agent():
    return login(*AGENT)


# Player handoff: auto ticket, no tag leak, reuse in same session
class TestPlayerHandoff:
    sid = f"test-{uuid.uuid4()}"
    state = {}

    def test_escalation_creates_ticket(self, demo):
        text, events = chat(demo, self.sid, "TEST_ my $50 UPI deposit ref UPI123 from 3 days ago never got credited, need a human")
        print("REPLY:", text)
        assert "[[" not in text and "TICKET:" not in text
        tick = [e["ticket"] for e in events if e.get("ticket")]
        assert tick, f"no ticket event; reply={text}"
        ref = tick[0]["reference"]
        assert ref.startswith("TCK-")
        assert f"Support ticket {ref} is open" in text
        self.state["ref"] = ref

    def test_ticket_in_support_list(self, demo):
        ref = self.state.get("ref") or pytest.skip("no ticket")
        ts = demo.get(f"{API}/support/tickets").json()
        t = next((x for x in ts if x["reference"] == ref), None)
        assert t, "ticket not in player list"
        assert t["source"] == "assistant"
        assert t["chat_session_id"] == self.sid
        assert t["category"] in ("deposit", "wallet")
        assert "UPI123" in t["messages"][0]["message"]
        assert "Opened by the AI assistant" in t["messages"][0]["message"]
        assert "_id" not in t
        self.state["id"] = t["id"]

    def test_history_has_no_tag(self, demo):
        h = demo.get(f"{API}/assistant/history", params={"session_id": self.sid}).json()
        assert len(h) == 2
        assert "[[" not in h[1]["content"]

    def test_second_escalation_reuses(self, demo):
        ref = self.state.get("ref") or pytest.skip("no ticket")
        text, events = chat(demo, self.sid, "Still nothing. Please connect me to a real person now, I want a human agent.")
        print("REPLY2:", text)
        assert "[[" not in text
        tick = [e["ticket"] for e in events if e.get("ticket")]
        if tick:
            assert tick[0]["reference"] == ref
        n = DB.tickets.count_documents({"chat_session_id": self.sid})
        assert n == 1, f"duplicate tickets: {n}"

    def test_normal_question_no_ticket(self, demo):
        sid = f"test-{uuid.uuid4()}"
        text, events = chat(demo, sid, "What is the fee for transferring credits?")
        print("FEE:", text)
        assert not any(e.get("ticket") for e in events)
        assert DB.tickets.count_documents({"chat_session_id": sid}) == 0
        assert "%" in text


# Agent chat access with agent data + escalation in agent support
class TestAgentChat:
    sid = f"test-{uuid.uuid4()}"

    def test_agent_commission_question(self, agent):
        me = agent.get(f"{API}/agent/me")
        print("AGENT DASH:", me.status_code, me.text[:400])
        text, events = chat(agent, self.sid, "what is my commission rate and how many players do I have?")
        print("AGENT:", text)
        assert "5" in text and "%" in text
        assert not any(e.get("ticket") for e in events)

    def test_agent_escalation(self, agent):
        text, events = chat(agent, self.sid, "My commission payout for last month was never received, I need a human from staff to check it.")
        print("AGENT ESC:", text)
        tick = [e["ticket"] for e in events if e.get("ticket")]
        assert tick, text
        ts = agent.get(f"{API}/support/tickets").json()
        t = next((x for x in ts if x["reference"] == tick[0]["reference"]), None)
        assert t and t["source"] == "assistant"
        assert t["messages"][0]["author_role"] == "agent"


# Roles + rate limit (no LLM calls)
class TestRolesAndRateLimit:
    def test_admin_staff_403_chat(self):
        for c in (ADMIN, STAFF):
            s = login(*c)
            r = s.post(f"{API}/assistant/chat", json={"session_id": "abcdefgh1234", "message": "hi"})
            assert r.status_code == 403

    def test_rate_limit_429(self):
        # use the agent account to avoid touching the player flow; docs inserted then removed by id
        s = login(*AGENT)
        uid = s.get(f"{API}/auth/me").json()["id"]
        ids = [f"TEST_rl_{uuid.uuid4()}" for _ in range(20)]
        ts = datetime.now(timezone.utc).isoformat()
        DB.chat_messages.insert_many([{"id": i, "user_id": uid, "session_id": "TEST_rl_session", "role": "user",
                                       "content": "TEST_ rate", "created_at": ts} for i in ids])
        try:
            r = s.post(f"{API}/assistant/chat", json={"session_id": "abcdefgh1234", "message": "hi"})
            assert r.status_code == 429
            assert "too fast" in r.json()["detail"]
        finally:
            DB.chat_messages.delete_many({"id": {"$in": ids}})


# Admin insights
class TestInsights:
    def test_player_agent_403(self, demo, agent):
        assert demo.get(f"{API}/admin/assistant/insights").status_code == 403
        assert agent.get(f"{API}/admin/assistant/insights").status_code == 403

    def test_unauth_401(self):
        assert requests.get(f"{API}/admin/assistant/insights").status_code == 401

    @pytest.mark.parametrize("who", [ADMIN, STAFF])
    def test_insights_shape(self, who):
        s = login(*who)
        for d in (7, 30, 90):
            r = s.get(f"{API}/admin/assistant/insights", params={"days": d})
            assert r.status_code == 200
            j = r.json()
            assert j["days"] == d
            for k in ("questions", "people", "chats", "tickets"):
                assert isinstance(j[k], int)
            assert isinstance(j["top_words"], list) and isinstance(j["recent"], list)
            if j["recent"]:
                assert {"question", "created_at", "name", "role"} <= set(j["recent"][0])
            assert all(q["count"] > 1 for q in j["top_questions"])

    def test_invalid_days(self):
        s = login(*ADMIN)
        assert s.get(f"{API}/admin/assistant/insights", params={"days": 0}).status_code == 422


# Regression: manual ticket creation via new_ticket
class TestManualTicket:
    def test_create_ticket(self, demo):
        r = demo.post(f"{API}/support/tickets", json={"subject": "TEST_ manual ticket", "category": "other", "message": "TEST_ hello from pytest"})
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["reference"].startswith("TCK-") and t["status"] == "open" and "_id" not in t
        assert "source" not in t or t["source"] != "assistant"
        ts = demo.get(f"{API}/support/tickets").json()
        assert any(x["id"] == t["id"] for x in ts)
        print("MANUAL TICKET:", t["id"])
