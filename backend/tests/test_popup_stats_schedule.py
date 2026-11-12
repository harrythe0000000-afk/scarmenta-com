# Popup click stats (unique view/click) + IST scheduling API tests (content.py)
import os
from datetime import datetime, timedelta, timezone
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
IST = timezone(timedelta(hours=5, minutes=30))

CREDS = {
    "admin": ("admin@aetheria.io", "Admin@12345"),
    "user": ("demo@aetheria.io", "Demo@12345"),
    "user2": ("agentplayer1@example.com", "Player@123"),
    "agent": ("agent@aetheria.io", "Agent@12345"),
}


def _login(role):
    s = requests.Session()
    email, pw = CREDS[role]
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"{role} login failed {r.status_code}: {r.text}")
    return s


def ist(delta_min):
    return (datetime.now(IST) + timedelta(minutes=delta_min)).replace(microsecond=0).isoformat()


@pytest.fixture(scope="module")
def S():
    return {k: _login(k) for k in CREDS}


@pytest.fixture(scope="module")
def created(S):
    ids = []
    yield ids
    for bid in ids:
        S["admin"].delete(f"{API}/admin/banners/{bid}")


def _create(S, created, **kw):
    body = {"title": "TEST_popup", "text": "t", "audience": ["user"], **kw}
    r = S["admin"].post(f"{API}/admin/banners", json=body)
    if r.status_code == 200:
        created.append(r.json()["id"])
    return r


def _admin_row(S, bid):
    rows = S["admin"].get(f"{API}/admin/banners").json()
    return next(b for b in rows if b["id"] == bid)


def _active_ids(s):
    r = s.get(f"{API}/banners/active")
    assert r.status_code == 200
    return [b["id"] for b in r.json()]


# --- Scheduling ---
def test_live_window_converts_ist_to_utc(S, created):
    st, en = ist(-60), ist(120)
    r = _create(S, created, title="TEST_live", starts_at=st, ends_at=en)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["starts_at"].endswith("+00:00")
    assert datetime.fromisoformat(d["starts_at"]) == datetime.fromisoformat(st)
    assert datetime.fromisoformat(d["ends_at"]) == datetime.fromisoformat(en)
    row = _admin_row(S, d["id"])
    assert row["starts_at"] == d["starts_at"] and row["ends_at"] == d["ends_at"]
    assert row["views"] == 0 and row["clicks"] == 0
    assert d["id"] in _active_ids(S["user"])
    pytest.live_id = d["id"]


def test_future_start_excluded(S, created):
    r = _create(S, created, title="TEST_future", starts_at=ist(120))
    assert r.status_code == 200, r.text
    assert r.json()["id"] not in _active_ids(S["user"])


def test_no_schedule_visible(S, created):
    r = _create(S, created, title="TEST_nosched")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["starts_at"] is None and d["ends_at"] is None
    assert d["id"] in _active_ids(S["user"])


def test_end_before_start_400(S, created):
    r = _create(S, created, starts_at=ist(120), ends_at=ist(60))
    assert r.status_code == 400 and "after start" in r.json()["detail"]


def test_end_in_past_400(S, created):
    r = _create(S, created, ends_at=ist(-5))
    assert r.status_code == 400 and "past" in r.json()["detail"]


def test_naive_datetime_400(S, created):
    r = _create(S, created, starts_at="2026-01-01T10:00:00")
    assert r.status_code == 400


def test_ended_popup_excluded_via_db(S, created):
    # create popup ending in 1 min, then backdate ends_at in mongo to simulate expiry
    import pymongo
    r = _create(S, created, title="TEST_ending", ends_at=ist(1))
    assert r.status_code == 200
    bid = r.json()["id"]
    db = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
    db.banners.update_one({"id": bid}, {"$set": {"ends_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}})
    assert bid not in _active_ids(S["user"])


# --- Events / unique stats ---
def test_event_requires_auth():
    r = requests.post(f"{API}/banners/{pytest.live_id}/event", json={"type": "view"})
    assert r.status_code == 401


def test_event_invalid_type_422(S):
    r = S["user"].post(f"{API}/banners/{pytest.live_id}/event", json={"type": "bogus"})
    assert r.status_code == 422


def test_event_wrong_role_404(S):
    # live popup audience is user only -> agent gets 404
    r = S["agent"].post(f"{API}/banners/{pytest.live_id}/event", json={"type": "view"})
    assert r.status_code == 404
    assert S["user"].post(f"{API}/banners/nonexistent/event", json={"type": "view"}).status_code == 404


def test_unique_view_click_counts(S):
    bid = pytest.live_id
    u = S["user"]
    for _ in range(3):
        assert u.post(f"{API}/banners/{bid}/event", json={"type": "view"}).status_code == 200
    assert u.post(f"{API}/banners/{bid}/event", json={"type": "click"}).status_code == 200
    assert u.post(f"{API}/banners/{bid}/event", json={"type": "click"}).status_code == 200
    row = _admin_row(S, bid)
    assert row["views"] == 1 and row["clicks"] == 1
    # re-login same user -> still 1
    u2 = _login("user")
    u2.post(f"{API}/banners/{bid}/event", json={"type": "view"})
    assert _admin_row(S, bid)["views"] == 1
    # second player increments
    p2 = S["user2"]
    assert p2.post(f"{API}/banners/{bid}/event", json={"type": "view"}).status_code == 200
    row = _admin_row(S, bid)
    assert row["views"] == 2 and row["clicks"] == 1


def test_agent_audience_counts(S, created):
    r = _create(S, created, title="TEST_both", audience=["user", "agent"], button_label="Go", button_url="/app")
    bid = r.json()["id"]
    assert bid in _active_ids(S["agent"])
    S["agent"].post(f"{API}/banners/{bid}/event", json={"type": "view"})
    S["agent"].post(f"{API}/banners/{bid}/event", json={"type": "click"})
    S["user"].post(f"{API}/banners/{bid}/event", json={"type": "view"})
    row = _admin_row(S, bid)
    assert row["views"] == 2 and row["clicks"] == 1


def test_admin_list_requires_admin(S):
    assert S["user"].get(f"{API}/admin/banners").status_code in (401, 403)
    assert S["agent"].get(f"{API}/admin/banners").status_code in (401, 403)
