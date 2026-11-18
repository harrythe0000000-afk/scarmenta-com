# InfinityAPI launch signature/form-field unit tests (httpx monkeypatched, no network)
import asyncio
import hashlib
import hmac
import os
import sys

import pytest
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
import bulkapi  # noqa: E402

KEY, SECRET = "TEST_key_abcdef", "TEST_secret_123456"


class FakeResp:
    def __init__(self, status, payload=None, text=None):
        self.status_code, self._p = status, payload
        self.text = text if text is not None else str(payload)

    def json(self):
        if self._p is None:
            raise ValueError("no json")
        return self._p


def make_client(resp, captured):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None, **k):
            captured["url"], captured["data"] = url, data
            return resp
    return FakeClient


@pytest.fixture
def patched(monkeypatch):
    async def noop():
        return None
    monkeypatch.setattr(bulkapi, "_ensure", noop)
    monkeypatch.setitem(bulkapi._CACHE, "token", KEY)
    monkeypatch.setitem(bulkapi._CACHE, "secret", SECRET)
    return monkeypatch


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_signature_and_fields(patched):
    cap = {}
    patched.setattr(bulkapi.httpx, "AsyncClient", make_client(FakeResp(200, {"ok": True, "game_url": "https://g.example/x", "request_id": "r1"}), cap))
    res = run(bulkapi.infinity_launch("scm_9111111111", 9500.5, "9417", "https://x/app/live-casino"))
    assert res == {"game_url": "https://g.example/x", "request_id": "r1"}
    assert cap["url"] == "https://infinityapipro.com/api/v1/launch.php"
    d = cap["data"]
    assert d["api_key"] == KEY and d["user_id"] == "scm_9111111111" and d["game_uid"] == "9417"
    assert d["balance"] == "9500.50" and d["currency_code"] == "INR" and d["redirect"] == "0"
    assert d["ts"].isdigit()
    exp = hmac.new(SECRET.encode(), f"{KEY}|scm_9111111111|9417|9500.50|{d['ts']}".encode(), hashlib.sha256).hexdigest()
    assert d["sig"] == exp


@pytest.mark.parametrize("resp", [
    FakeResp(200, {"ok": False, "error": "invalid_api_key"}),
    FakeResp(403, {"ok": False, "error": "ip_not_whitelisted"}),
    FakeResp(500, {"ok": True, "game_url": "https://a"}),
    FakeResp(200, None, text="<html>"),
    FakeResp(200, {"ok": True, "game_url": "http://insecure"}),
    FakeResp(200, {"ok": True}),
])
def test_bad_responses_raise(patched, resp):
    patched.setattr(bulkapi.httpx, "AsyncClient", make_client(resp, {}))
    with pytest.raises(bulkapi.LaunchError):
        run(bulkapi.infinity_launch("scm_1", 1.0, "9417", "https://x"))


def test_error_code_passthrough(patched):
    patched.setattr(bulkapi.httpx, "AsyncClient", make_client(FakeResp(200, {"ok": False, "error": "invalid_api_key"}), {}))
    with pytest.raises(bulkapi.LaunchError) as e:
        run(bulkapi.infinity_launch("scm_1", 1.0, "9417", "https://x"))
    assert e.value.code == "invalid_api_key"


def test_not_configured(monkeypatch):
    async def noop():
        return None
    monkeypatch.setattr(bulkapi, "_ensure", noop)
    monkeypatch.setitem(bulkapi._CACHE, "token", "")
    monkeypatch.setitem(bulkapi._CACHE, "secret", "")
    with pytest.raises(bulkapi.LaunchError) as e:
        run(bulkapi.infinity_launch("scm_1", 1.0, "9417", "https://x"))
    assert e.value.code == "not_configured"
