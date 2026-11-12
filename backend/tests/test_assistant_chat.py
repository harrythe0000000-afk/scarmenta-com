# AI assistant chat (SSE) + history isolation tests
import json
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
DEMO = ("demo@aetheria.io", "Demo@12345")
OTHER = ("agentplayer1@example.com", "Player@123")
ADMIN = ("admin@aetheria.io", "Admin@12345")
STAFF = ("staff@aetheria.io", "Staff@12345")
AGENT = ("agent@aetheria.io", "Agent@12345")


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    return s


def chat(s, sid, msg):
    r = s.post(f"{API}/assistant/chat", json={"session_id": sid, "message": msg}, stream=True, timeout=90)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    text, done, events = "", False, []
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
        text += ev["delta"]
    assert done
    return text, events


@pytest.fixture(scope="module")
def demo():
    return login(*DEMO)


@pytest.fixture(scope="module")
def sid():
    return f"test-{uuid.uuid4()}"


class TestAuthAndValidation:
    def test_unauth_chat(self):
        r = requests.post(f"{API}/assistant/chat", json={"session_id": "abcdefgh1234", "message": "hi"})
        assert r.status_code == 401

    def test_unauth_history(self):
        r = requests.get(f"{API}/assistant/history", params={"session_id": "abcdefgh1234"})
        assert r.status_code == 401

    @pytest.mark.parametrize("creds", [ADMIN, STAFF, AGENT])
    def test_non_player_403(self, creds):
        s = login(*creds)
        r = s.post(f"{API}/assistant/chat", json={"session_id": "abcdefgh1234", "message": "hi"})
        assert r.status_code == 403

    def test_empty_message_422(self, demo):
        r = demo.post(f"{API}/assistant/chat", json={"session_id": "abcdefgh1234", "message": ""})
        assert r.status_code == 422

    def test_bad_session_400(self, demo):
        r = demo.post(f"{API}/assistant/chat", json={"session_id": "bad session!!", "message": "hi"})
        assert r.status_code == 400

    def test_short_session_422(self, demo):
        r = demo.post(f"{API}/assistant/chat", json={"session_id": "abc", "message": "hi"})
        assert r.status_code == 422


class TestChatFlow:
    def test_balance_and_memory(self, demo, sid):
        me = demo.get(f"{API}/auth/me").json()
        u = me.get("user", me)
        bal = u.get("promo_balance")
        text, events = chat(demo, sid, "What is my credit balance?")
        print("REPLY1:", text)
        assert len(events) > 1  # streamed in multiple chunks
        assert text.strip()
        if bal is not None:
            assert f"{bal:,.0f}".split(".")[0] in text.replace("$", "") or f"{bal:g}" in text
        text2, _ = chat(demo, sid, "Can I withdraw that amount as cash?")
        print("REPLY2:", text2)
        assert "withdraw" in text2.lower() or "no" in text2.lower()
        text3, _ = chat(demo, sid, "What was the first question I asked you in this chat?")
        print("REPLY3:", text3)
        assert "balance" in text3.lower()

    def test_history_persisted(self, demo, sid):
        h = demo.get(f"{API}/assistant/history", params={"session_id": sid}).json()
        assert len(h) == 6
        assert [m["role"] for m in h] == ["user", "assistant"] * 3
        assert h[0]["content"] == "What is my credit balance?"
        assert all("_id" not in m for m in h)

    def test_history_isolated(self, sid):
        other = login(*OTHER)
        h = other.get(f"{API}/assistant/history", params={"session_id": sid})
        assert h.status_code == 200
        assert h.json() == []

    def test_new_session_empty(self, demo):
        h = demo.get(f"{API}/assistant/history", params={"session_id": f"test-{uuid.uuid4()}"}).json()
        assert h == []
