# Catalog-sync cron, broken-game handling, session-result popup API and my-rounds history (iteration 26)
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

import pymongo
import pytest
import requests
import yaml
from dotenv import dotenv_values

FE = dotenv_values("/app/frontend/.env")
BE = dotenv_values("/app/backend/.env")
BASE_URL = FE["REACT_APP_BACKEND_URL"].rstrip("/")
SECRET = BE["WEBHOOK_CRON_SECRET"]
mdb = pymongo.MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]
RUN_IDS, ROUNDS = [], []
TAG = "TEST_" + uuid.uuid4().hex[:6]


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
def demo():
    return login("demo@aetheria.io", "Demo@12345")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    u = mdb.users.find_one({"email": "demo@aetheria.io"}, {"_id": 0, "id": 1, "promo_balance": 1})
    bal = u["promo_balance"]
    yield
    for rnd in ROUNDS:
        mdb.live_events.delete_many({"user_id": u["id"], "game_round": rnd})
        mdb.live_rounds.delete_many({"user_id": u["id"], "game_round": {"$regex": f":{rnd}:"}})
        mdb.live_callbacks.delete_many({"game_round": rnd})
        mdb.transactions.delete_many({"user_id": u["id"], "type": "live_round", "description": {"$regex": "Dragon Tiger"},
                                      "created_at": {"$gte": START}})
    for rid in RUN_IDS:
        mdb.cron_runs.delete_one({"run_id": rid})
    mdb.users.update_one({"id": u["id"]}, {"$set": {"promo_balance": bal}})
    # restore game 6312 broken state if a toggle test changed it
    mdb.live_games.update_one({"game_uid": "6312"}, {"$set": {"active": False, "broken": True}, "$unset": {"admin_off": ""}})


START = datetime.now(timezone.utc).isoformat()


# ---- crons.yml ----
def test_crons_yml():
    c = yaml.safe_load(open("/app/.emergent/crons.yml"))["crons"]
    assert len(c) == 2
    assert sorted(x["cron"] for x in c) == ["0 2 * * *", "0 6 * * *"]
    assert all(x["timezone"] == "Asia/Kolkata" and x["endpoint"].endswith("/api/cron/catalog-sync") and x["method"] == "POST" for x in c)


# ---- cron auth ----
def test_cron_no_auth():
    r = requests.post(f"{BASE_URL}/api/cron/catalog-sync", json={})
    assert r.status_code == 401 and r.json()["ok"] is False


def test_cron_wrong_secret():
    r = requests.post(f"{BASE_URL}/api/cron/catalog-sync", headers={"Authorization": "Bearer nope"}, json={})
    assert r.status_code == 401


def test_cron_run_and_duplicate(admin):
    rid = f"{TAG}-run"
    RUN_IDS.append(rid)
    h = {"Authorization": f"Bearer {SECRET}", "X-Webhook-Id": rid}
    t = time.time()
    r = requests.post(f"{BASE_URL}/api/cron/catalog-sync", headers=h, json={})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert time.time() - t < 8
    run = None
    for _ in range(30):
        runs = admin.get(f"{BASE_URL}/api/admin/live/sync-runs").json()
        run = next((x for x in runs if x["run_id"] == rid), None)
        if run and run["status"] == "done":
            break
        time.sleep(2)
    assert run and run["status"] == "done", run
    res = run["results"]
    print(res)
    assert "Casino Game (CG)" in res and "Evolution Live" in res
    for v in res.values():
        assert "error" not in v and v["total"] > 0
    r2 = requests.post(f"{BASE_URL}/api/cron/catalog-sync", headers=h, json={})
    assert r2.status_code == 200 and r2.json().get("duplicate") is True
    # broken game must stay off after sync
    g = mdb.live_games.find_one({"game_uid": "6312"})
    assert g["broken"] is True and g["active"] is False
    # admin list exposes broken flag
    lst = admin.get(f"{BASE_URL}/api/admin/live/games").json()
    row = next(x for x in lst if x["game_uid"] == "6312")
    assert row["broken"] is True and row["active"] is False
    # player list hides it


def test_sync_requires_admin(demo):
    assert demo.get(f"{BASE_URL}/api/admin/live/sync-runs").status_code in (401, 403)


# ---- broken game probe / provider test ----
def test_probe_game_not_found_keeps_provider(admin):
    r = admin.post(f"{BASE_URL}/api/admin/live/test", json={"game_uid": "6312"})
    assert r.status_code == 200
    d = r.json()
    print("probe:", d)
    if not d.get("game_missing"):
        pytest.skip(f"InfinityAPI did not report game not found for 6312: {d.get('detail')} - provider test skipped to avoid disabling provider")
    prov = next(p for p in admin.get(f"{BASE_URL}/api/admin/live/providers").json() if p["name"] == "Evolution Live")
    r = admin.post(f"{BASE_URL}/api/admin/live/providers/{prov['id']}/test", json={"game_uid": "6312"})
    assert r.status_code == 200, r.text
    print("provider test:", r.json())
    prov2 = next(p for p in admin.get(f"{BASE_URL}/api/admin/live/providers").json() if p["name"] == "Evolution Live")
    if not prov2["enabled"]:
        admin.patch(f"{BASE_URL}/api/admin/live/providers/{prov['id']}", json={"enabled": True})
    assert prov2["enabled"] is True


def test_toggle_clears_broken(admin, demo):
    gid = mdb.live_games.find_one({"game_uid": "6312"})["id"]
    r = admin.patch(f"{BASE_URL}/api/admin/live/games/{gid}", json={"active": True})
    assert r.status_code == 200
    g = mdb.live_games.find_one({"game_uid": "6312"})
    assert g["broken"] is False and g["active"] is True
    assert any(x["id"] == gid for x in demo.get(f"{BASE_URL}/api/live/games").json())
    # restore
    mdb.live_games.update_one({"game_uid": "6312"}, {"$set": {"active": False, "broken": True}, "$unset": {"admin_off": ""}})
    assert not any(x["id"] == gid for x in demo.get(f"{BASE_URL}/api/live/games").json())


# ---- callbacks -> session result & history ----
def _cb_url(admin):
    return admin.get(f"{BASE_URL}/api/admin/live/status").json()["callback_url"]


def _send(admin, rnd, bet, win):
    ROUNDS.append(rnd)
    pid = mdb.users.find_one({"email": "demo@aetheria.io"})["bulk_player_id"]
    u = urlparse(_cb_url(admin))
    url = f"{BASE_URL}{u.path}?token={parse_qs(u.query)['token'][0]}"
    return requests.post(url, json={"member_account": f"scm_{pid}", "game_uid": "9418", "game_round": rnd,
                                    "serial_number": f"S-{rnd}", "bet_amount": bet, "win_amount": win,
                                    "timestamp": datetime.now(timezone.utc).isoformat()})


def test_session_result_win_and_loss(admin, demo):
    since = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    bal0 = demo.get(f"{BASE_URL}/api/auth/me").json().get("promo_balance")
    r = _send(admin, f"{TAG}-W", 95, 285)
    assert r.status_code == 200, r.text
    d = demo.get(f"{BASE_URL}/api/live/session-result", params={"since": since}).json()
    print(d, bal0)
    assert d["events"] == 1 and d["bet_inr"] == 95 and d["win_inr"] == 285 and d["net_inr"] == 190
    assert d["net_usd"] > 0
    since2 = datetime.now(timezone.utc).isoformat()
    time.sleep(0.5)
    r = _send(admin, f"{TAG}-L", 190, 0)
    assert r.status_code == 200
    d2 = demo.get(f"{BASE_URL}/api/live/session-result", params={"since": since2}).json()
    assert d2["events"] == 1 and d2["net_inr"] == -190 and d2["net_usd"] < 0
    # history
    rows = demo.get(f"{BASE_URL}/api/live/my-rounds").json()
    mine = [x for x in rows if TAG in x["game_round"]]
    assert len(mine) == 2
    w = next(x for x in mine if "-W" in x["game_round"])
    assert w["bet_inr"] == 95 and w["win_inr"] == 285 and w["net_inr"] == 190 and w["game_name"] == "Dragon Tiger"
    assert "user_id" not in w and "_id" not in w


def test_session_result_bad_since(demo):
    assert demo.get(f"{BASE_URL}/api/live/session-result", params={"since": "garbage"}).status_code == 400
    assert demo.get(f"{BASE_URL}/api/live/session-result").status_code == 422


def test_my_rounds_requires_auth():
    assert requests.get(f"{BASE_URL}/api/live/my-rounds").status_code == 401


def test_my_rounds_empty_for_other_user():
    s = login("agentplayer1@example.com", "Player@123")
    assert s.get(f"{BASE_URL}/api/live/my-rounds").json() == []
