# BULKAPI host switch (bulkapi.org -> bulkapi.site): status, admin probe, player launch, provider test auto-disable, callbacks
import os
import uuid

import pymongo
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]
TOKEN = os.environ.get("BULK_TOKEN", "")
BULK_ERR = "Token not found or secret key missing in database."
STATE = {"prov": None, "game": None, "uid": None, "rounds": [], "orig_balance": None}


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}")
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin@aetheria.io", "Admin@12345")


@pytest.fixture(scope="module")
def player():
    return login("demo@aetheria.io", "Demo@12345")


@pytest.fixture(scope="module", autouse=True)
def setup_cleanup(admin):
    u = mdb.users.find_one({"email": "demo@aetheria.io"})
    STATE["orig_balance"] = u.get("promo_balance")
    name = f"TEST_SiteProv_{uuid.uuid4().hex[:5]}"
    r = admin.post(f"{BASE_URL}/api/admin/live/providers", json={"name": name})
    assert r.status_code == 200, r.text
    STATE["prov"] = r.json()
    STATE["uid"] = f"TEST_uid_{uuid.uuid4().hex[:8]}"
    g = admin.post(f"{BASE_URL}/api/admin/live/games", json={"name": "TEST_Site Game", "provider": name, "game_uid": STATE["uid"]})
    assert g.status_code == 200, g.text
    STATE["game"] = g.json()
    yield
    gid, pname = STATE["game"]["id"], name
    mdb.live_sessions.delete_many({"game_id": gid})
    mdb.live_games.delete_one({"id": gid})
    mdb.live_provider_tests.delete_many({"provider": pname})
    mdb.live_providers.delete_one({"id": STATE["prov"]["id"]})
    for rnd in STATE["rounds"]:
        mdb.live_rounds.delete_many({"game_round": rnd})
        mdb.live_callbacks.delete_many({"game_round": rnd})
        mdb.transactions.delete_many({"reference": {"$regex": f"^LIVE-{rnd[:20]}"}})
    mdb.users.update_one({"email": "demo@aetheria.io"}, {"$set": {"promo_balance": STATE["orig_balance"]}})


def test_status_reachable(admin):
    r = admin.get(f"{BASE_URL}/api/admin/live/status")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["reachable"] is True
    assert d["launch_url"] == "https://bulkapi.site/launch_game/"
    assert d["token_is_url"] is True
    assert d["source"] == "server"


def test_admin_probe_bulkapi_error(admin):
    r = admin.post(f"{BASE_URL}/api/admin/live/test", json={"game_uid": "TEST"}, timeout=40)
    assert r.status_code == 200, r.text
    d = r.json()
    print(d)
    assert d["ok"] is False
    assert d["status"] == 200
    assert BULK_ERR in d["detail"]


def test_provider_test_disables(admin):
    pid = STATE["prov"]["id"]
    mdb.live_providers.update_one({"id": pid}, {"$set": {"enabled": True}})
    r = admin.post(f"{BASE_URL}/api/admin/live/providers/{pid}/test", json={}, timeout=40)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is False and d["status"] == 200 and d["game_uid"] == STATE["uid"]
    assert BULK_ERR in d["detail"]
    doc = mdb.live_providers.find_one({"id": pid})
    assert doc["enabled"] is False
    assert doc["last_test"]["ok"] is False
    # cannot re-enable via API after failed test
    assert admin.patch(f"{BASE_URL}/api/admin/live/providers/{pid}", json={"enabled": True}).status_code == 400


def test_player_launch_url_and_follow(player):
    mdb.live_providers.update_one({"id": STATE["prov"]["id"]}, {"$set": {"enabled": True}})
    r = player.post(f"{BASE_URL}/api/live/launch", json={"game_id": STATE["game"]["id"]})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith("https://bulkapi.site/launch_game/?")
    assert f"game_uid={STATE['uid']}" in url
    f = requests.get(url, timeout=30, allow_redirects=True)
    print(f.status_code, f.text[:200])
    assert f.status_code == 200
    assert BULK_ERR in f.text
    mdb.live_providers.update_one({"id": STATE["prov"]["id"]}, {"$set": {"enabled": False}})


def test_callback_and_duplicate():
    if not TOKEN:
        pytest.skip("BULK_TOKEN not set")
    rnd = f"TEST_rnd_{uuid.uuid4().hex[:10]}"
    STATE["rounds"].append(rnd)
    pid = mdb.users.find_one({"email": "demo@aetheria.io"})["bulk_player_id"]
    before = mdb.users.find_one({"email": "demo@aetheria.io"})["promo_balance"]
    form = {"token": TOKEN, "game_round": rnd, "mobile": pid, "bet_amount": "95", "win_amount": "190", "game_uid": STATE["uid"]}
    r = requests.post(f"{BASE_URL}/api/game_callback.php", data=form)
    assert r.status_code == 200 and r.text == "ok"
    after = mdb.users.find_one({"email": "demo@aetheria.io"})["promo_balance"]
    rate = mdb.live_rounds.find_one({"game_round": rnd})["rate"]
    assert round(after - before, 2) == round(95 / rate, 2)
    r2 = requests.post(f"{BASE_URL}/api/game_callback.php", data=form)
    assert r2.status_code == 200 and r2.text == "ok"
    assert mdb.users.find_one({"email": "demo@aetheria.io"})["promo_balance"] == after
    last = mdb.live_callbacks.find({"game_round": rnd}).sort("created_at", -1).limit(1)[0]
    assert "duplicate" in last["result"]
    bad = requests.post(f"{BASE_URL}/api/game_callback.php", data={**form, "token": "wrong"})
    assert bad.status_code == 403
