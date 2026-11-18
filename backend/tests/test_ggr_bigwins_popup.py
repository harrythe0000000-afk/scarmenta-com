# Iteration 27: GGR alert, big-wins feed, session-result (win/even/loss) and note_ggr helper
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pymongo
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
KEY = "infinity_ggr_alert"


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}")
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin@aetheria.io", "Admin@12345")


@pytest.fixture(scope="module")
def staff():
    return login("staff@aetheria.io", "Staff@12345")


@pytest.fixture(scope="module")
def demo():
    return login("demo@aetheria.io", "Demo@12345")


@pytest.fixture(scope="module")
def demo_id():
    return mdb.users.find_one({"email": "demo@aetheria.io"})["id"]


# ---- GGR alert endpoint ----
class TestGgrAlert:
    def test_requires_staff(self, demo):
        assert demo.get(f"{API}/admin/live/ggr-alert").status_code == 403
        assert requests.get(f"{API}/admin/live/ggr-alert").status_code == 401

    def test_empty_then_set(self, admin, staff):
        existing = mdb.settings.find_one({"key": KEY})
        if existing:
            pytest.skip("real alert present; not touching")
        assert admin.get(f"{API}/admin/live/ggr-alert").json() == {}
        at = datetime.now(timezone.utc).isoformat()
        mdb.settings.insert_one({"key": KEY, "message": "TEST_Provider GGR Balance is depleted", "at": at})
        try:
            for s in (admin, staff):
                d = s.get(f"{API}/admin/live/ggr-alert").json()
                assert d == {"message": "TEST_Provider GGR Balance is depleted", "at": at}
        finally:
            mdb.settings.delete_one({"key": KEY, "message": "TEST_Provider GGR Balance is depleted"})
        assert admin.get(f"{API}/admin/live/ggr-alert").json() == {}


# ---- note_ggr helper (unit, no real API) ----
class TestNoteGgr:
    def test_note_ggr_set_ignore_clear(self):
        if mdb.settings.find_one({"key": KEY}):
            pytest.skip("real alert present")
        sys.path.insert(0, "/app/backend")
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        import bulkapi

        async def run():
            await bulkapi.note_ggr(bulkapi.LaunchError("Game provider error", 400, "other failure"))
            assert await bulkapi.db.settings.find_one({"key": KEY}) is None
            await bulkapi.note_ggr(bulkapi.LaunchError("Provider GGR Balance is depleted", 400, ""))
            doc = await bulkapi.db.settings.find_one({"key": KEY})
            assert doc and doc["message"] == "Provider GGR Balance is depleted" and doc["at"]
            await bulkapi.note_ggr(bulkapi.LaunchError("Game provider error", 400, '{"msg":"ggr low"}'))
            doc2 = await bulkapi.db.settings.find_one({"key": KEY})
            assert doc2["message"] == "Game provider error"
            await bulkapi.note_ggr(None)
            assert await bulkapi.db.settings.find_one({"key": KEY}) is None
        try:
            asyncio.run(run())
        finally:
            mdb.settings.delete_one({"key": KEY})


# ---- Big wins feed ----
class TestBigWins:
    def test_auth_required(self):
        assert requests.get(f"{API}/live/big-wins").status_code == 401

    def test_masked_and_filtered(self, demo, demo_id):
        now = datetime.now(timezone.utc).isoformat()
        rounds = [
            {"game_round": "TEST-BW-1", "user_id": demo_id, "game_name": "Lightning Roulette", "provider": "Evolution Live",
             "bet_inr": 100, "win_inr": 1500, "net_inr": 1400, "updated_at": now, "settled": True},
            {"game_round": "TEST-BW-2", "user_id": demo_id, "game_name": "Small Win", "provider": "Ezugi",
             "bet_inr": 100, "win_inr": 150, "net_inr": 50, "updated_at": now, "settled": True},
        ]
        mdb.live_rounds.insert_many([dict(r) for r in rounds])
        try:
            data = demo.get(f"{API}/live/big-wins").json()
            assert isinstance(data, list) and len(data) <= 15
            mine = [w for w in data if w["game"] == "Lightning Roulette" and w["net_inr"] == 1400]
            assert mine, data
            assert mine[0]["player"] == "De***"
            assert all(w["net_inr"] >= 100 for w in data)
            assert not any(w["game"] == "Small Win" for w in data)
            assert all(set(w) == {"player", "game", "net_inr", "at"} for w in data)
        finally:
            mdb.live_rounds.delete_many({"game_round": {"$in": ["TEST-BW-1", "TEST-BW-2"]}, "user_id": demo_id})


# ---- session-result (popup data) ----
class TestSessionResult:
    def _seed(self, demo_id, since, bet, win):
        key = f"TEST-EV-{uuid.uuid4()}"
        ts = (since + timedelta(seconds=2)).isoformat()
        mdb.live_events.insert_one({"user_id": demo_id, "created_at": ts, "bet_inr": bet, "win_inr": win,
                                    "delta_usd": round((win - bet) / 95, 2), "event_key": key})
        return key

    @pytest.mark.parametrize("bet,win,net", [(100, 300, 200), (200, 200, 0), (200, 0, -200)])
    def test_result(self, demo, demo_id, bet, win, net):
        since = datetime.now(timezone.utc) + timedelta(days=1)  # future window isolates from real events
        key = self._seed(demo_id, since, bet, win)
        try:
            d = demo.get(f"{API}/live/session-result", params={"since": since.isoformat()}).json()
            assert d["events"] == 1 and d["net_inr"] == net and d["bet_inr"] == bet and d["win_inr"] == win
        finally:
            mdb.live_events.delete_one({"event_key": key})

    def test_bad_since(self, demo):
        assert demo.get(f"{API}/live/session-result", params={"since": "nope"}).status_code == 400


# ---- Player game list includes new providers ----
class TestPlayerProviders:
    def test_new_providers_listed(self, demo):
        r = demo.get(f"{API}/live/games")
        assert r.status_code == 200
        body = r.json()
        games = body if isinstance(body, list) else body.get("games", [])
        provs = {g.get("provider") for g in games}
        print("providers:", provs, "games:", len(games))
        for p in ["Evolution Live (Asia)", "Ezugi", "PragmaticPlayLive-EU", "Spribe", "JILI"]:
            assert p in provs, f"{p} missing from player games"
