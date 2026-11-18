# InfinityAPI integration API tests: status, creds, test-launch, catalog, callback ledger, player launch, transfer pause
# Run serially: pytest tests/test_infinity_api.py -n 0
import os
import re
import uuid
from datetime import datetime, timezone

import pymongo
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
DEMO = db.users.find_one({"email": "demo@aetheria.io"})
PID = DEMO["bulk_player_id"]
MEMBER = f"scm_{PID}"
RUN = uuid.uuid4().hex[:8]


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin@aetheria.io", "Admin@12345")


@pytest.fixture(scope="module")
def player():
    return login("demo@aetheria.io", "Demo@12345")


@pytest.fixture(scope="module")
def cb_url(admin):
    return admin.get(f"{BASE_URL}/api/admin/live/status").json()["callback_url"]


def bal():
    return round(db.users.find_one({"id": DEMO["id"]})["promo_balance"], 2)


# ---- status ----
def test_status(admin):
    a = admin.get(f"{BASE_URL}/api/admin/live/status").json()
    b = admin.get(f"{BASE_URL}/api/admin/live/status").json()
    assert a["launch_url"] == "https://infinityapipro.com/api/v1/launch.php"
    assert a["reachable"] is True
    m = re.search(r"/api/infinity/callback\?token=(.+)$", a["callback_url"])
    assert m and len(m.group(1)) >= 32
    assert a["callback_url"] == b["callback_url"]
    assert a["source"] == "server"


# ---- catalog without key ----
def test_catalog_without_key(admin):
    r = admin.get(f"{BASE_URL}/api/admin/live/catalog/providers")
    assert r.status_code == 400, r.text


# ---- creds + test + catalog with fake key ----
def test_fake_creds_flow(admin):
    r = admin.put(f"{BASE_URL}/api/admin/live/credentials", json={"api_token": f"TEST_fakekey_{RUN}", "secret_key": f"TEST_fakesecret_{RUN}"})
    assert r.status_code == 200, r.text
    try:
        st = admin.get(f"{BASE_URL}/api/admin/live/status").json()
        assert st["source"] == "admin panel" and st["token_set"] and st["secret_set"]
        t = admin.post(f"{BASE_URL}/api/admin/live/test", json={"game_uid": "9417"}).json()
        print("TEST LAUNCH:", t)
        assert t["ok"] is False and t["status"] and t["detail"]
        c = admin.get(f"{BASE_URL}/api/admin/live/catalog/providers")
        print("CATALOG:", c.status_code, c.text)
        assert c.status_code == 502
        # NOTE: preview ingress replaces 502 bodies with an HTML page; JSON detail only visible internally
        if c.headers.get("content-type", "").startswith("application/json"):
            assert "InfinityAPI" in c.json()["detail"]
    finally:
        d = admin.delete(f"{BASE_URL}/api/admin/live/credentials")
        assert d.status_code == 200 and d.json()["source"] == "server"
    assert admin.get(f"{BASE_URL}/api/admin/live/status").json()["source"] == "server"


# ---- callback ledger ----
def post_cb(url, body, raw=None):
    if raw is not None:
        return requests.post(url, data=raw, headers={"Content-Type": "application/json"})
    return requests.post(url, json=body)


def ev(rnd, serial, bet, win, **kw):
    return {"member_account": MEMBER, "game_uid": "9417", "game_round": rnd, "serial_number": serial,
            "bet_amount": bet, "win_amount": win, "timestamp": "2026-01-10 10:00:00", **kw}


def test_callback_loss_win_dup_conflict(cb_url):
    rnd = f"TEST_R_{RUN}"
    b0 = bal()
    r = post_cb(cb_url, ev(rnd, f"S1_{RUN}", 95, 0))
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert bal() == round(b0 - 1, 2)
    r = post_cb(cb_url, ev(rnd, f"S2_{RUN}", 0, 190))
    assert r.status_code == 200 and r.json()["ok"] is True
    assert bal() == round(b0 + 1, 2)
    r = post_cb(cb_url, ev(rnd, f"S2_{RUN}", 0, 190))
    assert r.status_code == 200 and r.json()["ok"] is True
    assert bal() == round(b0 + 1, 2)
    r = post_cb(cb_url, ev(rnd, f"S2_{RUN}", 0, 950))
    assert r.status_code == 409 and r.json() == {"ok": False}
    assert bal() == round(b0 + 1, 2)
    rd = db.live_rounds.find_one({"game_round": f"9417:{rnd}:{PID}"})
    assert rd and rd["bet_inr"] == 95 and rd["win_inr"] == 190 and rd["applied_usd"] == 1


def test_callback_no_serial_uses_timestamp(cb_url):
    rnd = f"TEST_T_{RUN}"
    b0 = bal()
    body = ev(rnd, None, 9.5, 0)
    body.pop("serial_number")
    assert post_cb(cb_url, body).status_code == 200
    assert post_cb(cb_url, body).status_code == 200  # duplicate
    assert bal() == round(b0 - 0.1, 2)


def test_callback_bad_token(cb_url):
    bad = cb_url.split("token=")[0] + "token=wrong"
    r = post_cb(bad, ev("TEST_X", "S", 1, 0))
    assert r.status_code == 403 and r.json() == {"ok": False}
    r = post_cb(cb_url.split("?")[0], ev("TEST_X", "S", 1, 0))
    assert r.status_code == 403


@pytest.mark.parametrize("bet,win", [(-1, 0), ("NaN", 0), (1.234, 0), (0, "abc"), (True, 0), ("1e400", 0)])
def test_callback_invalid_amounts(cb_url, bet, win):
    b0 = bal()
    r = post_cb(cb_url, ev(f"TEST_I_{RUN}", f"SI_{bet}", bet, win))
    assert r.status_code == 400, (bet, r.text)
    assert bal() == b0


def test_callback_unknown_member_and_missing(cb_url):
    r = post_cb(cb_url, {**ev("TEST_U", "SU", 1, 0), "member_account": "scm_0000000000"})
    assert r.status_code == 404
    body = ev("TEST_M", None, 1, 0)
    body.pop("serial_number"); body.pop("timestamp")
    assert post_cb(cb_url, body).status_code == 400
    for f in ("member_account", "game_uid", "game_round"):
        b = ev("TEST_M", "SM", 1, 0); b.pop(f)
        assert post_cb(cb_url, b).status_code == 400
    assert post_cb(cb_url, None, raw="not json").status_code == 400
    assert post_cb(cb_url, None, raw="[1,2]").status_code == 400


def test_callback_logs(admin):
    logs = admin.get(f"{BASE_URL}/api/admin/live/callbacks").json()
    mine = [l for l in logs if str(l.get("game_round") or "").endswith(RUN)]
    assert len(mine) >= 4
    assert any(l["http_status"] == 409 for l in mine)
    assert any(l["result"].startswith("duplicate") for l in mine)
    failed = admin.get(f"{BASE_URL}/api/admin/live/callbacks?failed=true").json()
    assert all(l["failed"] for l in failed)
    assert not any("token" in (l.get("fields") or {}) for l in logs)


# ---- player launch with invalid keys ----
def test_player_launch_fails_502(admin, player):
    prov = db.live_providers.find_one({"name": "Evolution"})
    gid = f"TEST_G_{RUN}"
    db.live_games.insert_one({"id": gid, "name": "TEST_Game", "provider": "Evolution", "game_uid": f"TEST_{RUN}", "active": True,
                              "deleted": False, "image_url": "https://example.com/x.png", "created_at": datetime.now(timezone.utc).isoformat()})
    db.live_providers.update_one({"_id": prov["_id"]}, {"$set": {"enabled": True}})
    admin.put(f"{BASE_URL}/api/admin/live/credentials", json={"api_token": f"TEST_fakekey_{RUN}", "secret_key": f"TEST_fakesecret_{RUN}"})
    try:
        games = player.get(f"{BASE_URL}/api/live/games").json()
        g = next(x for x in games if x["id"] == gid)
        assert g["image_url"] == "https://example.com/x.png" and "game_uid" not in g
        r = player.post(f"{BASE_URL}/api/live/launch", json={"game_id": gid})
        print("LAUNCH:", r.status_code, r.text)
        assert r.status_code == 502
        s = admin.get(f"{BASE_URL}/api/admin/live/sessions?status=failed").json()
        assert any(x["game_id"] == gid and x["status"] == "failed" and "could not be opened" in x["reason"] for x in s)
    finally:
        admin.delete(f"{BASE_URL}/api/admin/live/credentials")
        db.live_providers.update_one({"_id": prov["_id"]}, {"$set": {"enabled": prov.get("enabled", False)}})
        db.live_games.delete_one({"id": gid})
        db.live_sessions.delete_many({"game_id": gid})


# ---- transfers paused ----
def test_transfer_paused(player):
    sid = f"TEST_S_{RUN}"
    body = {"to_email": f"test_nobody_{RUN}@example.com", "to_password": "x", "amount": 1}
    db.live_sessions.insert_one({"id": sid, "user_id": DEMO["id"], "status": "launched", "created_at": datetime.now(timezone.utc).isoformat()})
    try:
        r = player.post(f"{BASE_URL}/api/transfers", json=body)
        assert r.status_code == 400 and "Transfers are paused" in r.json()["detail"]
    finally:
        db.live_sessions.delete_one({"id": sid})
    r = player.post(f"{BASE_URL}/api/transfers", json=body)
    assert "Transfers are paused" not in r.text
