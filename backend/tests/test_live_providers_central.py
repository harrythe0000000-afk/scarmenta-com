# BULKAPI centralized config + live providers (CRUD, test-before-enable gating, player filter), server-ip, launch encryption
import base64
import json
import os
import uuid
from urllib.parse import parse_qs, urlparse

import pymongo
import pytest
import requests
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
SECRET = (os.environ.get("API_SECRET") or os.environ.get("BULKAPI_SECRET_KEY", "")).strip()
PROVS, GAMES = [], []


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
def staff():
    return login("staff@aetheria.io", "Staff@12345")


@pytest.fixture(scope="module")
def player():
    return login("demo@aetheria.io", "Demo@12345")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for g in GAMES:
        mdb.live_sessions.delete_many({"game_id": g})
        mdb.live_games.delete_one({"id": g})
    for p in PROVS:
        doc = mdb.live_providers.find_one({"id": p})
        if doc:
            mdb.live_provider_tests.delete_many({"provider": doc["name"]})
        mdb.live_providers.delete_one({"id": p})


@pytest.fixture(scope="module")
def prov(admin):
    name = f"TEST_Prov_{uuid.uuid4().hex[:5]}"
    r = admin.post(f"{BASE_URL}/api/admin/live/providers", json={"name": name})
    assert r.status_code == 200, r.text
    d = r.json()
    PROVS.append(d["id"])
    return d


class TestProviders:
    def test_list_seeded(self, staff, player):
        r = staff.get(f"{BASE_URL}/api/admin/live/providers")
        assert r.status_code == 200
        names = {p["name"] for p in r.json()}
        assert {"Evolution", "Ezugi", "Pragmatic", "JILI", "JDB", "SPRIBE"} <= names
        assert all("_id" not in p and p["endpoint"].endswith("/launch_game") for p in r.json())
        assert player.get(f"{BASE_URL}/api/admin/live/providers").status_code == 403

    def test_add_dup_rbac(self, admin, staff, prov):
        assert prov["enabled"] is False and prov["provider_id"] == prov["name"].lower()
        assert admin.post(f"{BASE_URL}/api/admin/live/providers", json={"name": prov["name"]}).status_code == 400
        assert staff.post(f"{BASE_URL}/api/admin/live/providers", json={"name": "TEST_x_staff"}).status_code == 403

    def test_enable_requires_test(self, admin, prov):
        r = admin.patch(f"{BASE_URL}/api/admin/live/providers/{prov['id']}", json={"enabled": True})
        assert r.status_code == 400 and "successful test" in r.json()["detail"]

    def test_probe_no_games(self, admin, prov):
        r = admin.post(f"{BASE_URL}/api/admin/live/providers/{prov['id']}/test", json={})
        assert r.status_code == 400

    def test_probe_with_game_records_failure(self, admin, prov):
        uid = f"TEST_uid_{uuid.uuid4().hex[:6]}"
        g = admin.post(f"{BASE_URL}/api/admin/live/games", json={"name": "TEST_Game", "provider": prov["name"], "game_uid": uid})
        assert g.status_code == 200, g.text
        GAMES.append(g.json()["id"])
        r = admin.post(f"{BASE_URL}/api/admin/live/providers/{prov['id']}/test", json={}, timeout=40)
        assert r.status_code == 200, r.text
        d = r.json()
        print("probe:", d)
        assert d["game_uid"] == uid and "ok" in d
        doc = mdb.live_providers.find_one({"id": prov["id"]})
        assert doc["last_test"]["game_uid"] == uid
        if not d["ok"]:
            assert doc["enabled"] is False

    def test_delete_with_games_blocked(self, admin, prov):
        assert admin.delete(f"{BASE_URL}/api/admin/live/providers/{prov['id']}").status_code == 400

    def test_unknown_provider_game_rejected(self, admin):
        r = admin.post(f"{BASE_URL}/api/admin/live/games", json={"name": "TEST_G", "provider": "TEST_NoSuch", "game_uid": "TEST_zz"})
        assert r.status_code == 400

    def test_404s(self, admin):
        assert admin.patch(f"{BASE_URL}/api/admin/live/providers/nope", json={"enabled": False}).status_code == 404
        assert admin.delete(f"{BASE_URL}/api/admin/live/providers/nope").status_code == 404


class TestGatingAndLaunch:
    def test_disabled_provider_hidden_and_blocked(self, player, prov):
        gid = GAMES[0]
        assert gid not in [x["id"] for x in player.get(f"{BASE_URL}/api/live/games").json()]
        r = player.post(f"{BASE_URL}/api/live/launch", json={"game_id": gid})
        assert r.status_code == 403

    def test_enabled_provider_launch_encrypted(self, player, prov, staff):
        mdb.live_providers.update_one({"id": prov["id"]}, {"$set": {"enabled": True}})
        gid = GAMES[0]
        assert gid in [x["id"] for x in player.get(f"{BASE_URL}/api/live/games").json()]
        r = player.post(f"{BASE_URL}/api/live/launch", json={"game_id": gid})
        assert r.status_code == 200, r.text
        url = r.json()["url"]
        launch = staff.get(f"{BASE_URL}/api/admin/live/status", timeout=30).json()["launch_url"]
        assert url.startswith(launch + "?")
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        if SECRET and not mdb.settings.find_one({"key": "bulkapi_creds"}):
            key = SECRET.encode()[:32].ljust(32, b"\0")
            dec = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
            raw = dec.update(base64.b64decode(q["payload"])) + dec.finalize()
            up = padding.PKCS7(128).unpadder()
            p = json.loads(up.update(raw) + up.finalize())
            assert p["user_id"] == q["user_id"] and p["game_uid"] == q["game_uid"] and str(p["timestamp"]) == q["timestamp"]


class TestCentralConfig:
    def test_status_uses_base_url(self, staff):
        d = staff.get(f"{BASE_URL}/api/admin/live/status", timeout=30).json()
        base = (os.environ.get("API_BASE_URL") or os.environ.get("BULKAPI_BASE_URL") or "").rstrip("/")
        if base:
            assert d["launch_url"] == base + "/launch_game"
        print("status:", {k: d[k] for k in ("source", "token_set", "secret_bytes", "reachable", "launch_url")})

    def test_server_ip(self, staff, player):
        r = staff.get(f"{BASE_URL}/api/admin/live/server-ip", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ip"].count(".") == 3 and d["domain"] == "scarmenta.com"
        assert player.get(f"{BASE_URL}/api/admin/live/server-ip").status_code == 403

    def test_creds_reject_url(self, admin):
        r = admin.put(f"{BASE_URL}/api/admin/live/credentials", json={"api_token": "https://x.com/cb.php"})
        assert r.status_code == 400
