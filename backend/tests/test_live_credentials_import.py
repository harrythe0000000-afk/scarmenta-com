# BULKAPI admin-panel credentials (encrypted save, masks, used by callbacks/launch) + bulk game import (CSV/XLSX)
import io
import os
import uuid
from urllib.parse import parse_qs, urlparse

import openpyxl
import pymongo
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ENV_TOKEN = os.environ.get("BULK_TOKEN")
MOBILE = "9111111111"
mdb = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
NEW_TOKEN = f"TEST_tok_{uuid.uuid4().hex[:12]}"
NEW_SECRET31 = "TEST_" + "s" * 26  # 31 chars
NEW_SECRET32 = "TEST_" + "k" * 27  # 32 chars
ROUNDS, GAME_UIDS = [], []


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
    mdb.settings.delete_one({"key": "bulkapi_creds"})
    mdb.audit_logs.delete_many({"action": "bulkapi_credentials_updated", "by": "admin@aetheria.io"})
    for rnd in ROUNDS:
        mdb.live_rounds.delete_many({"game_round": rnd})
        mdb.live_callbacks.delete_many({"game_round": rnd})
        mdb.transactions.delete_many({"reference": f"LIVE-{rnd[:20]}"})
    ids = [g["id"] for g in mdb.live_games.find({"game_uid": {"$in": GAME_UIDS}}, {"id": 1})]
    mdb.live_sessions.delete_many({"game_id": {"$in": ids}})
    mdb.live_games.delete_many({"game_uid": {"$in": GAME_UIDS}})
    mdb.users.update_one({"email": "demo@aetheria.io"}, {"$set": {"promo_balance": 1039}})


def cb(rnd, token):
    return requests.post(f"{BASE_URL}/api/bulkapi/callback", data={
        "mobile": MOBILE, "bet_amount": "0", "win_amount": "0", "game_uid": "TEST_cb", "game_round": rnd, "token": token})


# ---- Credentials ----
class TestCredentials:
    def test_permissions_and_validation(self, admin, staff, player):
        assert staff.put(f"{BASE_URL}/api/admin/live/credentials", json={"api_token": "x"}).status_code == 403
        assert player.put(f"{BASE_URL}/api/admin/live/credentials", json={"api_token": "x"}).status_code == 403
        assert admin.put(f"{BASE_URL}/api/admin/live/credentials", json={}).status_code == 400
        assert admin.put(f"{BASE_URL}/api/admin/live/credentials", json={"api_token": "  ", "secret_key": ""}).status_code == 400
        for bad in ("https://bulkapi.org/x", "http://a", "www.bulkapi.org", "HTTPS://X"):
            r = admin.put(f"{BASE_URL}/api/admin/live/credentials", json={"api_token": bad})
            assert r.status_code == 400, bad
        assert mdb.settings.find_one({"key": "bulkapi_creds"}) is None

    def test_save_encrypted_masked_warning(self, admin):
        r = admin.put(f"{BASE_URL}/api/admin/live/credentials", json={"api_token": NEW_TOKEN, "secret_key": NEW_SECRET31})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["token_mask"] == "••••" + NEW_TOKEN[-4:]
        assert d["secret_mask"] == "••••" + NEW_SECRET31[-4:]
        assert "31" in d["warning"]
        assert NEW_TOKEN not in r.text and NEW_SECRET31 not in r.text
        doc = mdb.settings.find_one({"key": "bulkapi_creds"})
        assert doc and doc["token_enc"] and doc["secret_enc"]
        assert NEW_TOKEN not in str(doc) and NEW_SECRET31 not in str(doc)

    def test_status_after_save(self, staff):
        d = staff.get(f"{BASE_URL}/api/admin/live/status", timeout=30).json()
        assert d["source"] == "admin panel"
        assert d["token_mask"] == "••••" + NEW_TOKEN[-4:]
        assert d["secret_mask"] == "••••" + NEW_SECRET31[-4:]
        assert d["secret_bytes"] == 31
        assert NEW_TOKEN not in str(d)

    def test_callback_uses_new_token(self):
        r1 = f"TEST_{uuid.uuid4().hex[:10]}"
        ROUNDS.append(r1)
        r = cb(r1, NEW_TOKEN)
        assert r.status_code == 200 and r.text == "ok", r.text
        if ENV_TOKEN:
            r2 = f"TEST_{uuid.uuid4().hex[:10]}"
            ROUNDS.append(r2)
            r = cb(r2, ENV_TOKEN)
            assert r.status_code == 403 and r.text == "invalid token"

    def test_launch_uses_new_token(self, admin, player):
        uid = f"TEST_cred_{uuid.uuid4().hex[:6]}"
        GAME_UIDS.append(uid)
        g = admin.post(f"{BASE_URL}/api/admin/live/games", json={"name": "TEST_CredGame", "provider": "Ezugi", "game_uid": uid}).json()
        r = player.post(f"{BASE_URL}/api/live/launch", json={"game_id": g["id"]})
        assert r.status_code == 200, r.text
        assert parse_qs(urlparse(r.json()["url"]).query)["token"][0] == NEW_TOKEN

    def test_partial_update_keeps_token(self, admin, staff):
        r = admin.put(f"{BASE_URL}/api/admin/live/credentials", json={"secret_key": NEW_SECRET32})
        assert r.status_code == 200
        assert r.json()["warning"] == ""
        assert r.json()["token_mask"] == "••••" + NEW_TOKEN[-4:]
        d = staff.get(f"{BASE_URL}/api/admin/live/status", timeout=30).json()
        assert d["secret_bytes"] == 32 and d["token_mask"] == "••••" + NEW_TOKEN[-4:]
        assert mdb.audit_logs.find_one({"action": "bulkapi_credentials_updated", "fields": ["secret"]})


# ---- Import ----
def up(s, name, data, ctype="text/csv"):
    return s.post(f"{BASE_URL}/api/admin/live/games/import", files={"file": (name, data, ctype)})


class TestImport:
    def test_csv_aliases_dupes_errors(self, admin, player):
        u1, u2, u3 = (f"TEST_imp_{uuid.uuid4().hex[:6]}" for _ in range(3))
        GAME_UIDS.extend([u1, u2, u3])
        csv = (f"\ufeffGame Name,Vendor,Game ID\nTEST_Imp One,Evolution,{u1}\nTEST_Imp Two,,{u2}\n"
               f"TEST_Imp Dup,Ezugi,{u1}\n,Ezugi,{u3}\nX,Ezugi,TEST_short\n\n")
        r = up(admin, "games.csv", csv.encode())
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["added"] == 2 and d["skipped"] == 1 and d["error_count"] == 2, d
        # re-import -> all skipped
        d2 = up(admin, "games.csv", csv.encode()).json()
        assert d2["added"] == 0 and d2["skipped"] == 3
        ag = {g["game_uid"]: g for g in admin.get(f"{BASE_URL}/api/admin/live/games").json()}
        assert ag[u1]["name"] == "TEST_Imp One" and ag[u1]["provider"] == "Evolution" and ag[u1]["active"] is True
        assert ag[u2]["provider"] == "Other"
        pg = player.get(f"{BASE_URL}/api/live/games").json()
        mine = [g for g in pg if g["id"] in (ag[u1]["id"], ag[u2]["id"])]
        assert len(mine) == 2 and all("game_uid" not in g for g in mine)

    def test_xlsx(self, admin):
        u1, u2 = f"TEST_x_{uuid.uuid4().hex[:6]}", f"TEST_x_{uuid.uuid4().hex[:6]}"
        GAME_UIDS.extend([u1, u2])
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["name", "provider", "uid"])
        ws.append(["TEST_Xl One", "Playtech", u1])
        ws.append(["TEST_Xl Two", "Iconic21", u2])
        buf = io.BytesIO()
        wb.save(buf)
        r = up(admin, "g.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        assert r.status_code == 200, r.text
        assert r.json()["added"] == 2
        uids = {g["game_uid"] for g in admin.get(f"{BASE_URL}/api/admin/live/games").json()}
        assert {u1, u2} <= uids

    def test_bad_files(self, admin, staff):
        assert up(staff, "g.csv", b"name,game_uid\nA1,b").status_code == 403
        assert up(admin, "g.txt", b"name,game_uid\nAA,b").status_code == 400
        assert up(admin, "g.csv", b"title,provider\nAA,b").status_code == 400
        assert up(admin, "g.csv", b"name,provider\nAA,b").status_code == 400
        assert up(admin, "g.csv", b"name,game_uid\n").status_code == 400
        assert up(admin, "g.xlsx", b"not an excel").status_code == 400
