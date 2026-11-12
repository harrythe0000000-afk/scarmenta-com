# Promo screenshot contest: upload, visibility, admin review, winner credit, staff permissions
import io
import os
import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = ("admin@aetheria.io", "Admin@12345")
DEMO = ("demo@aetheria.io", "Demo@12345")
STAFF = ("staff@aetheria.io", "Staff@12345")
AGENT = ("agent@aetheria.io", "Agent@12345")
OTHER = ("agentplayer1@example.com", "Player@123")

CREATED = []


def login(email, pwd):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd})
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code} {r.text[:100]}")
    return s


@pytest.fixture(scope="module")
def admin():
    return login(*ADMIN)


@pytest.fixture(scope="module")
def demo():
    return login(*DEMO)


@pytest.fixture(scope="module")
def staff():
    return login(*STAFF)


@pytest.fixture(scope="module")
def other():
    return login(*OTHER)


def png_bytes(color=(200, 50, 50)):
    b = io.BytesIO()
    Image.new("RGB", (60, 40), color).save(b, "PNG")
    return b.getvalue()


def upload(s, data=None, name="shot.png", ctype="image/png", caption="TEST_whatsapp status"):
    files = {"file": (name, data if data is not None else png_bytes(), ctype)}
    d = {"caption": caption} if caption else {}
    r = s.post(f"{BASE_URL}/api/contest/entries", files=files, data=d)
    if r.status_code == 200:
        CREATED.append(r.json()["id"])
    return r


# Upload validation
def test_upload_ok(demo):
    r = upload(demo)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "pending" and j["bonus"] == 0
    assert j["caption"] == "TEST_whatsapp status"
    assert "***" in j["name"]
    assert "user_email" not in j


def test_upload_no_caption(demo):
    r = upload(demo, caption=None)
    assert r.status_code == 200
    assert r.json()["caption"] is None


def test_upload_non_image_ext(demo):
    r = upload(demo, data=b"hello", name="x.txt", ctype="text/plain")
    assert r.status_code == 400


def test_upload_fake_png(demo):
    r = upload(demo, data=b"not really a png" * 10, name="fake.png")
    assert r.status_code == 400
    assert "valid image" in r.json()["detail"]


def test_upload_too_big(demo):
    r = upload(demo, data=png_bytes() + b"\0" * (5 * 1024 * 1024 + 10), name="big.png")
    assert r.status_code == 400
    assert "5 MB" in r.json()["detail"]


def test_upload_admin_staff_agent_forbidden(admin, staff):
    assert upload(admin).status_code == 403
    assert upload(staff).status_code == 403
    ag = login(*AGENT)
    assert upload(ag).status_code == 403


def test_upload_unauth():
    r = requests.post(f"{BASE_URL}/api/contest/entries", files={"file": ("a.png", png_bytes(), "image/png")})
    assert r.status_code == 401


# Own entries + image access
def test_me_and_image_access(demo, other, staff, admin):
    eid = CREATED[0]
    me = demo.get(f"{BASE_URL}/api/contest/me").json()
    assert any(e["id"] == eid for e in me)
    r = demo.get(f"{BASE_URL}/api/contest/image/{eid}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/png")
    Image.open(io.BytesIO(r.content)).verify()
    assert other.get(f"{BASE_URL}/api/contest/image/{eid}").status_code == 404
    assert all(e["id"] != eid for e in other.get(f"{BASE_URL}/api/contest/me").json())
    assert staff.get(f"{BASE_URL}/api/contest/image/{eid}").status_code == 200
    assert admin.get(f"{BASE_URL}/api/contest/image/{eid}").status_code == 200
    assert demo.get(f"{BASE_URL}/api/contest/image/nonexistent").status_code == 404


# Admin listing
def test_admin_list(admin, staff, demo):
    r = admin.get(f"{BASE_URL}/api/admin/contest/entries?status=pending")
    assert r.status_code == 200
    j = r.json()
    assert set(j["counts"]) == {"pending", "winner", "rejected"}
    e = next(x for x in j["entries"] if x["id"] == CREATED[0])
    assert e["user_email"] == "demo@aetheria.io" and e["name"] == "Demo Player"
    assert staff.get(f"{BASE_URL}/api/admin/contest/entries").status_code == 200
    assert demo.get(f"{BASE_URL}/api/admin/contest/entries").status_code == 403
    assert admin.get(f"{BASE_URL}/api/admin/contest/entries?status=bogus").status_code == 422


# Winner flow
def test_win_flow(admin, staff, demo, other):
    eid = CREATED[0]
    before = demo.get(f"{BASE_URL}/api/auth/me").json()
    pb = before.get("promo_balance", before.get("user", {}).get("promo_balance"))
    assert staff.post(f"{BASE_URL}/api/admin/contest/entries/{eid}/win", json={"amount": 5}).status_code == 403
    assert admin.post(f"{BASE_URL}/api/admin/contest/entries/{eid}/win", json={"amount": 0}).status_code == 422
    assert admin.post(f"{BASE_URL}/api/admin/contest/entries/{eid}/win", json={"amount": 20000}).status_code == 422
    r = admin.post(f"{BASE_URL}/api/admin/contest/entries/{eid}/win", json={"amount": 12.345})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "winner" and r.json()["bonus"] == 12.35
    r2 = admin.post(f"{BASE_URL}/api/admin/contest/entries/{eid}/win", json={"amount": 12})
    assert r2.status_code == 400
    after = demo.get(f"{BASE_URL}/api/auth/me").json()
    pa = after.get("promo_balance", after.get("user", {}).get("promo_balance"))
    assert round(pa - pb, 2) == 12.35
    # other player can now see image
    assert other.get(f"{BASE_URL}/api/contest/image/{eid}").status_code == 200
    # winners gallery masked
    w = other.get(f"{BASE_URL}/api/contest/winners").json()
    we = next(x for x in w if x["id"] == eid)
    assert we["name"] == "De***o" and we["bonus"] == 12.35 and "user_email" not in we
    # reject after winner -> 400
    assert staff.post(f"{BASE_URL}/api/admin/contest/entries/{eid}/reject", json={}).status_code == 400


def test_win_transaction_created(admin):
    from pymongo import MongoClient
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))["test_database"]
    txs = list(db.transactions.find({"reference": CREATED[0]}, {"_id": 0}))
    assert len(txs) == 1
    assert txs[0]["type"] == "contest_bonus" and txs[0]["wallet"] == "credit" and txs[0]["amount"] == 12.35


def test_staff_reject(staff, admin, demo):
    eid = CREATED[1]
    r = staff.post(f"{BASE_URL}/api/admin/contest/entries/{eid}/reject", json={"note": "TEST_blurry"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert staff.post(f"{BASE_URL}/api/admin/contest/entries/{eid}/reject", json={}).status_code == 400
    assert admin.post(f"{BASE_URL}/api/admin/contest/entries/{eid}/win", json={"amount": 5}).status_code == 400
    rej = admin.get(f"{BASE_URL}/api/admin/contest/entries?status=rejected").json()
    e = next(x for x in rej["entries"] if x["id"] == eid)
    assert e["note"] == "TEST_blurry"
    me = demo.get(f"{BASE_URL}/api/contest/me").json()
    assert next(x for x in me if x["id"] == eid)["status"] == "rejected"
