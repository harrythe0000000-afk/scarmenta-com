# BULKAPI live casino: launch, callbacks (idempotency/updates/errors), admin reports, rate, games CRUD
import os
import uuid
from urllib.parse import parse_qs, urlparse

import pymongo
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOKEN = os.environ.get("BULK_TOKEN")
MOBILE = "9111111111"
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
CREATED_ROUNDS, CREATED_GAMES = [], []


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin@aetheria.io", "Admin@12345")


@pytest.fixture(scope="module")
def staff():
    return login("staff@aetheria.io", "Staff@12345")


@pytest.fixture(scope="module")
def player():
    return login("demo@aetheria.io", "Demo@12345")


def bal():
    return float(mdb.users.find_one({"email": "demo@aetheria.io"})["promo_balance"])


@pytest.fixture(scope="module")
def game(admin):
    uid = f"TEST_uid_{uuid.uuid4().hex[:6]}"
    r = admin.post(f"{BASE_URL}/api/admin/live/games", json={"name": "TEST_Roulette", "provider": "Evolution", "game_uid": uid})
    assert r.status_code == 200, r.text
    g = r.json()
    CREATED_GAMES.append(g["id"])
    yield g


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    start = bal()
    yield
    for rnd in CREATED_ROUNDS:
        mdb.live_rounds.delete_many({"game_round": rnd})
        mdb.live_callbacks.delete_many({"game_round": rnd})
        mdb.transactions.delete_many({"reference": f"LIVE-{rnd[:20]}"})
    mdb.live_callbacks.delete_many({"game_round": {"$regex": "^TEST_"}})
    mdb.live_callbacks.delete_many({"fields.game_uid": {"$regex": "^TEST_"}})
    for gid in CREATED_GAMES:
        mdb.live_sessions.delete_many({"game_id": gid})
        mdb.live_games.delete_one({"id": gid})
    mdb.live_sessions.delete_many({"game_id": "TEST_nonexistent"})
    mdb.users.update_one({"email": "demo@aetheria.io"}, {"$set": {"promo_balance": 1039}})
    mdb.settings.update_one({"key": "live_casino"}, {"$set": {"inr_rate": 95}})


def cb(path, rnd, bet, win, token=None, mobile=MOBILE, uid="TEST_cb"):
    data = {"mobile": mobile, "bet_amount": bet, "win_amount": win, "game_uid": uid, "game_round": rnd,
            "token": TOKEN if token is None else token, "wallet_before": "100", "wallet_after": "100",
            "change": str(float(win) - float(bet)) if str(bet).replace('.', '').isdigit() else "0",
            "currency_code": "INR", "timestamp": "1700000000000"}
    data = {k: v for k, v in data.items() if v is not None}
    return requests.post(f"{BASE_URL}{path}", data=data)


def new_round():
    r = f"TEST_{uuid.uuid4().hex[:10]}"
    CREATED_ROUNDS.append(r)
    return r


# ---- Launch ----
class TestLaunch:
    def test_launch_url(self, player, game):
        r = player.post(f"{BASE_URL}/api/live/launch", json={"game_id": game["id"]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["url"].startswith("https://bulkapi.org/launch_game?")
        q = parse_qs(urlparse(d["url"]).query)
        for k in ("user_id", "wallet_amount", "game_uid", "token", "timestamp", "payload"):
            assert k in q, k
        assert q["user_id"][0] == MOBILE
        assert q["game_uid"][0] == game["game_uid"]
        assert abs(d["wallet_inr"] - round(bal() * 95, 2)) < 0.01
        s = mdb.live_sessions.find_one({"game_id": game["id"], "status": "launched"})
        assert s and s["wallet_inr"] == d["wallet_inr"]

    def test_launch_inactive_logged_failed(self, player, admin, game):
        admin.patch(f"{BASE_URL}/api/admin/live/games/{game['id']}", json={"active": False})
        r = player.post(f"{BASE_URL}/api/live/launch", json={"game_id": game["id"]})
        admin.patch(f"{BASE_URL}/api/admin/live/games/{game['id']}", json={"active": True})
        assert r.status_code == 404
        # inactive game logged with game=None
        assert mdb.live_sessions.find_one({"user_email": "demo@aetheria.io", "status": "failed", "reason": "Game not available"})
        mdb.live_sessions.delete_many({"user_email": "demo@aetheria.io", "status": "failed", "reason": "Game not available", "game_id": None})

    def test_launch_zero_balance(self, player, game):
        orig = bal()
        mdb.users.update_one({"email": "demo@aetheria.io"}, {"$set": {"promo_balance": 0}})
        try:
            r = player.post(f"{BASE_URL}/api/live/launch", json={"game_id": game["id"]})
        finally:
            mdb.users.update_one({"email": "demo@aetheria.io"}, {"$set": {"promo_balance": orig}})
        assert r.status_code == 400
        assert mdb.live_sessions.find_one({"game_id": game["id"], "status": "failed"})

    def test_admin_cannot_launch(self, admin, game):
        assert admin.post(f"{BASE_URL}/api/live/launch", json={"game_id": game["id"]}).status_code == 403

    def test_player_games_hide_uid(self, player, game):
        r = player.get(f"{BASE_URL}/api/live/games")
        assert r.status_code == 200
        g = [x for x in r.json() if x["id"] == game["id"]]
        assert g and "game_uid" not in g[0]


# ---- Callback ----
@pytest.mark.parametrize("path", ["/api/game_callback.php", "/api/bulkapi/callback"])
class TestCallback:
    def test_win_loss_dup_update(self, path):
        if not TOKEN:
            pytest.skip("no token")
        b0 = bal()
        r1 = new_round()
        r = cb(path, r1, "100", "290")
        assert r.status_code == 200 and r.text == "ok"
        assert abs(bal() - (b0 + 190 / 95)) < 0.001
        # exact duplicate
        r = cb(path, r1, "100", "290")
        assert r.text == "ok"
        assert abs(bal() - (b0 + 2)) < 0.001
        # update same round different amounts -> diff only (net 0 now -> -2)
        r = cb(path, r1, "100", "5")
        assert r.text == "ok"
        assert abs(bal() - (b0 - 95 / 95)) < 0.001
        # losing round
        r2 = new_round()
        b1 = bal()
        r = cb(path, r2, "190", "0")
        assert r.text == "ok"
        assert abs(bal() - (b1 - 2)) < 0.001
        rr = mdb.live_rounds.find_one({"game_round": r1})
        assert rr["callbacks"] == 3 and rr["settled"] is True

    def test_errors(self, path):
        assert (r := cb(path, new_round(), "1", "1", token="bad")).status_code == 403 and r.text == "invalid token"
        r = requests.post(f"{BASE_URL}{path}", data={"token": TOKEN, "bet_amount": "1", "win_amount": "1", "game_uid": "TEST_cb"})
        assert r.status_code == 400
        assert cb(path, new_round(), "1", "2", mobile="9000000001").status_code == 404


class TestCallbackEdge:
    def test_nan_amount_rejected(self):
        b0 = bal()
        rnd = new_round()
        r = cb("/api/bulkapi/callback", rnd, "nan", "0")
        after = bal()
        mdb.live_rounds.delete_many({"game_round": rnd})
        mdb.transactions.delete_many({"reference": f"LIVE-{rnd[:20]}"})
        mdb.users.update_one({"email": "demo@aetheria.io"}, {"$set": {"promo_balance": b0}})
        assert r.status_code == 400, f"nan accepted: {r.status_code} {r.text}, balance after={after}"

    def test_json_body(self):
        b0 = bal()
        rnd = new_round()
        r = requests.post(f"{BASE_URL}/api/bulkapi/callback", json={"mobile": MOBILE, "bet_amount": 95, "win_amount": 190,
                                                                       "game_uid": "TEST_cb", "game_round": rnd, "token": TOKEN})
        assert r.text == "ok"
        assert abs(bal() - (b0 + 1)) < 0.001


# ---- Admin ----
class TestAdmin:
    def test_status(self, staff):
        r = staff.get(f"{BASE_URL}/api/admin/live/status", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("reachable", "failed_callbacks", "unsettled", "token_set", "secret_bytes", "inr_rate"):
            assert k in d
        assert d["reachable"] is False and d["token_set"] is True

    def test_rate(self, admin, staff):
        assert staff.put(f"{BASE_URL}/api/admin/live/rate", json={"inr_rate": 90}).status_code == 403
        assert admin.put(f"{BASE_URL}/api/admin/live/rate", json={"inr_rate": 1}).status_code == 422
        assert admin.put(f"{BASE_URL}/api/admin/live/rate", json={"inr_rate": 1001}).status_code == 422
        r = admin.put(f"{BASE_URL}/api/admin/live/rate", json={"inr_rate": 90})
        assert r.status_code == 200 and r.json()["inr_rate"] == 90
        assert admin.get(f"{BASE_URL}/api/admin/live/status", timeout=30).json()["inr_rate"] == 90
        admin.put(f"{BASE_URL}/api/admin/live/rate", json={"inr_rate": 95})

    def test_test_launch(self, admin, staff):
        assert staff.post(f"{BASE_URL}/api/admin/live/test", json={"game_uid": "x"}).status_code == 403
        r = admin.post(f"{BASE_URL}/api/admin/live/test", json={"game_uid": "TEST_x"}, timeout=40)
        assert r.status_code == 200
        assert r.json()["ok"] is False and "reach" in r.json()["detail"]

    def test_reports(self, staff, game):
        s = staff.get(f"{BASE_URL}/api/admin/live/sessions", params={"user": "demo", "status": "launched"}).json()
        assert s and all(x["status"] == "launched" and x["user_email"].startswith("demo") for x in s)
        w = staff.get(f"{BASE_URL}/api/admin/live/rounds", params={"result": "win"}).json()
        assert w and all(x["net_inr"] > 0 for x in w)
        lo = staff.get(f"{BASE_URL}/api/admin/live/rounds", params={"user": "demo", "result": "loss"}).json()
        assert lo and all(x["net_inr"] < 0 for x in lo)
        p = staff.get(f"{BASE_URL}/api/admin/live/players").json()
        assert any(x["player_id"] == MOBILE for x in p)
        f = staff.get(f"{BASE_URL}/api/admin/live/callbacks", params={"failed": "true"}).json()
        assert f and all(x["failed"] for x in f)
        assert all("token" not in x["fields"] for x in f)
        allc = staff.get(f"{BASE_URL}/api/admin/live/callbacks").json()
        assert len(allc) > len(f)

    def test_games_crud(self, admin, staff):
        assert staff.post(f"{BASE_URL}/api/admin/live/games", json={"name": "TEST_x", "provider": "Ezugi", "game_uid": "TEST_s"}).status_code == 403
        uid = f"TEST_crud_{uuid.uuid4().hex[:5]}"
        r = admin.post(f"{BASE_URL}/api/admin/live/games", json={"name": "TEST_Crud", "provider": "Ezugi", "game_uid": uid})
        assert r.status_code == 200
        gid = r.json()["id"]
        CREATED_GAMES.append(gid)
        assert admin.post(f"{BASE_URL}/api/admin/live/games", json={"name": "TEST_Crud", "provider": "Ezugi", "game_uid": uid}).status_code == 400
        assert admin.patch(f"{BASE_URL}/api/admin/live/games/{gid}", json={"active": False}).status_code == 200
        assert any(g["id"] == gid and g["active"] is False for g in staff.get(f"{BASE_URL}/api/admin/live/games").json())
        assert admin.delete(f"{BASE_URL}/api/admin/live/games/{gid}").status_code == 200
        assert not any(g["id"] == gid for g in admin.get(f"{BASE_URL}/api/admin/live/games").json())
        assert admin.patch(f"{BASE_URL}/api/admin/live/games/nope", json={"active": True}).status_code == 404
