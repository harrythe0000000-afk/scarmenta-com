# Popup banners + Terms re-accept API tests (content.py)
import base64
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==")

CREDS = {
    "admin": ("admin@aetheria.io", "Admin@12345"),
    "user": ("demo@aetheria.io", "Demo@12345"),
    "staff": ("staff@aetheria.io", "Staff@12345"),
    "agent": ("agent@aetheria.io", "Agent@12345"),
}


def _login(role):
    s = requests.Session()
    email, pw = CREDS[role]
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"{role} login failed {r.status_code}: {r.text}")
    return s


@pytest.fixture(scope="module")
def sessions():
    return {k: _login(k) for k in CREDS}


@pytest.fixture(scope="module")
def created(sessions):
    ids = []
    yield ids
    for bid in ids:
        sessions["admin"].delete(f"{API}/admin/banners/{bid}")


# --- Image upload ---
def test_upload_png_and_serve(sessions, created):
    a = sessions["admin"]
    r = a.post(f"{API}/admin/banners/image", files={"file": ("TEST_img.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    fid = r.json()["image_id"]
    g = requests.get(f"{API}/banners/image/{fid}")
    assert g.status_code == 200
    assert g.headers["content-type"].startswith("image/png")
    assert g.content == PNG
    pytest.image_id = fid


def test_upload_non_image_rejected(sessions):
    r = sessions["admin"].post(f"{API}/admin/banners/image", files={"file": ("TEST.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_image_404(sessions):
    assert requests.get(f"{API}/banners/image/nonexistent-id").status_code == 404


# --- RBAC ---
@pytest.mark.parametrize("role", ["staff", "user", "agent"])
def test_admin_banner_endpoints_forbidden(sessions, role):
    s = sessions[role]
    assert s.get(f"{API}/admin/banners").status_code == 403
    assert s.post(f"{API}/admin/banners", json={"title": "TEST_x", "audience": ["user"]}).status_code == 403
    assert s.post(f"{API}/admin/banners/image", files={"file": ("a.png", PNG, "image/png")}).status_code == 403
    assert s.get(f"{API}/admin/terms").status_code == 403
    assert s.post(f"{API}/admin/terms/require-reaccept").status_code == 403


def test_unauth_active_banners(sessions):
    assert requests.get(f"{API}/banners/active").status_code == 401


# --- Validation ---
def test_validation(sessions):
    a = sessions["admin"]
    assert a.post(f"{API}/admin/banners", json={"title": "TEST_v", "audience": ["user"], "button_label": "Go"}).status_code == 400
    assert a.post(f"{API}/admin/banners", json={"title": "TEST_v", "audience": ["user"], "button_url": "/app"}).status_code == 400
    assert a.post(f"{API}/admin/banners", json={"title": "TEST_v", "audience": []}).status_code == 422
    assert a.post(f"{API}/admin/banners", json={"title": "TEST_v", "audience": ["staff"]}).status_code == 422
    assert a.post(f"{API}/admin/banners", json={"title": "TEST_v", "audience": ["user"], "button_label": "Go", "button_url": "javascript:alert(1)"}).status_code == 400
    assert a.post(f"{API}/admin/banners", json={"title": "TEST_v", "audience": ["user"], "image_id": "nope"}).status_code == 400


# --- CRUD + role filtering ---
def test_create_and_role_filter(sessions, created):
    a = sessions["admin"]
    r = a.post(f"{API}/admin/banners", json={"title": "TEST_UserPopup", "text": "hi", "audience": ["user"],
                                             "button_label": "Deposit", "button_url": "/app/deposits",
                                             "image_id": getattr(pytest, "image_id", None)})
    assert r.status_code == 200, r.text
    ub = r.json()
    created.append(ub["id"])
    assert ub["audience"] == ["user"] and ub["active"] is True
    r = a.post(f"{API}/admin/banners", json={"title": "TEST_AgentPopup", "audience": ["agent"]})
    agb = r.json()
    created.append(agb["id"])
    r = a.post(f"{API}/admin/banners", json={"title": "TEST_BothPopup", "audience": ["agent", "user", "user"]})
    bb = r.json()
    created.append(bb["id"])
    assert bb["audience"] == ["agent", "user"]

    listed = [b["id"] for b in a.get(f"{API}/admin/banners").json()]
    assert ub["id"] in listed and agb["id"] in listed

    u = [b["id"] for b in sessions["user"].get(f"{API}/banners/active").json()]
    assert ub["id"] in u and bb["id"] in u and agb["id"] not in u
    g = [b["id"] for b in sessions["agent"].get(f"{API}/banners/active").json()]
    assert agb["id"] in g and bb["id"] in g and ub["id"] not in g
    assert sessions["staff"].get(f"{API}/banners/active").json() == []
    assert sessions["admin"].get(f"{API}/banners/active").json() == []

    # toggle off
    assert a.patch(f"{API}/admin/banners/{ub['id']}", json={"active": False}).status_code == 200
    u = [b["id"] for b in sessions["user"].get(f"{API}/banners/active").json()]
    assert ub["id"] not in u
    assert a.patch(f"{API}/admin/banners/{ub['id']}", json={"active": True}).status_code == 200
    # delete
    assert a.delete(f"{API}/admin/banners/{bb['id']}").status_code == 200
    u = [b["id"] for b in sessions["user"].get(f"{API}/banners/active").json()]
    assert bb["id"] not in u
    assert bb["id"] not in [b["id"] for b in a.get(f"{API}/admin/banners").json()]
    assert a.patch(f"{API}/admin/banners/{bb['id']}", json={"active": True}).status_code == 404
    assert a.delete(f"{API}/admin/banners/missing-id").status_code == 404


# --- Terms re-accept ---
def test_terms_flow(sessions):
    a, u = sessions["admin"], sessions["user"]
    assert a.post(f"{API}/admin/terms/require-reaccept").status_code == 200
    st = a.get(f"{API}/admin/terms").json()
    assert st["pending"] >= 1 and st["total"] == st["pending"] + st["accepted"]
    assert u.get(f"{API}/terms/status").json()["required"] is True
    assert sessions["agent"].get(f"{API}/terms/status").json()["required"] is True
    assert sessions["staff"].get(f"{API}/terms/status").json()["required"] is False
    assert u.post(f"{API}/terms/accept", json={"terms_version": ""}).status_code == 422
    assert u.post(f"{API}/terms/accept", json={"terms_version": "2026-11-12"}).status_code == 200
    assert u.get(f"{API}/terms/status").json()["required"] is False
    st2 = a.get(f"{API}/admin/terms").json()
    assert st2["pending"] == st["pending"] - 1
    # re-accept agent too so it doesn't block UI later
    sessions["agent"].post(f"{API}/terms/accept", json={"terms_version": "2026-11-12"})


def test_register_requires_terms():
    r = requests.post(f"{API}/auth/register", json={"name": "TEST_x", "email": "test_noterms_x@example.com",
                                                    "password": "Passw0rd!123", "accepted_terms": False})
    assert r.status_code in (400, 422)
