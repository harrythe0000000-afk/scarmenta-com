# Admin login access + site_url origin whitelist (iteration 8)
import os
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = ("admin@aetheria.io", "Admin@12345")
STAFF = ("staff@aetheria.io", "Staff@12345")
DEMO = ("demo@aetheria.io", "Demo@12345")


def login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    return s, r


# Auth roles
class TestRoles:
    def test_admin_login(self):
        s, r = login(*ADMIN)
        assert r.status_code == 200
        assert r.json()["role"] == "admin" if "role" in r.json() else r.json()["user"]["role"] == "admin"
        assert "access_token" in s.cookies

    def test_staff_login(self):
        s, r = login(*STAFF)
        assert r.status_code == 200
        me = s.get(f"{BASE_URL}/api/auth/me").json()
        assert me["role"] == "staff"

    def test_player_login_then_logout_me_401(self):
        s, r = login(*DEMO)
        assert r.status_code == 200
        assert s.post(f"{BASE_URL}/api/auth/logout").status_code == 200
        s.cookies.clear()
        assert s.get(f"{BASE_URL}/api/auth/me").status_code == 401

    def test_wrong_password(self):
        s, r = login(DEMO[0], "Wrong@99999")
        assert r.status_code == 401
        # clear failed counter
        _, ok = login(*DEMO)
        assert ok.status_code == 200

    def test_player_forbidden_admin_api(self):
        s, _ = login(*DEMO)
        assert s.get(f"{BASE_URL}/api/admin/stats").status_code == 403

    def test_staff_forbidden_settings(self):
        s, _ = login(*STAFF)
        assert s.get(f"{BASE_URL}/api/admin/settings").status_code == 403


# Site URL whitelist
class TestSiteUrl:
    def test_forgot_password_whitelisted_origin(self):
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": "nobody_TEST@example.com"},
                          headers={"Origin": "https://scarmenta.com"})
        assert r.status_code == 200

    def test_forgot_password_evil_origin(self):
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": "nobody_TEST@example.com"},
                          headers={"Origin": "https://evil.example"})
        assert r.status_code == 200

    def test_referral_link_whitelisted(self):
        s, _ = login(*DEMO)
        r = s.get(f"{BASE_URL}/api/referrals/me", headers={"Origin": "https://scarmenta.com"})
        assert r.status_code == 200
        assert r.json()["link"].startswith("https://scarmenta.com/register?ref=")

    def test_referral_link_www_whitelisted(self):
        s, _ = login(*DEMO)
        r = s.get(f"{BASE_URL}/api/referrals/me", headers={"Origin": "https://www.scarmenta.com"})
        assert r.json()["link"].startswith("https://www.scarmenta.com/register?ref=")

    def test_referral_link_evil_falls_back(self):
        s, _ = login(*DEMO)
        r = s.get(f"{BASE_URL}/api/referrals/me", headers={"Origin": "https://evil.example"})
        assert r.status_code == 200
        assert r.json()["link"].startswith(BASE_URL + "/register?ref=")

    def test_referral_link_no_origin(self):
        s, _ = login(*DEMO)
        r = s.get(f"{BASE_URL}/api/referrals/me")
        assert r.json()["link"].startswith(BASE_URL + "/register?ref=")

    def test_cors_whitelisted_and_evil(self):
        ok = requests.options(f"{BASE_URL}/api/auth/me", headers={"Origin": "https://scarmenta.com",
                              "Access-Control-Request-Method": "GET"})
        assert ok.headers.get("access-control-allow-origin") == "https://scarmenta.com"
        assert ok.headers.get("access-control-allow-credentials") == "true"
        bad = requests.options(f"{BASE_URL}/api/auth/me", headers={"Origin": "https://evil.example",
                               "Access-Control-Request-Method": "GET"})
        assert bad.headers.get("access-control-allow-origin") != "https://evil.example"


# Unit: core.site_url
def test_site_url_unit(monkeypatch):
    import sys
    sys.path.insert(0, "/app/backend")
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    import core

    class R:
        def __init__(self, o): self.headers = {"origin": o} if o else {}
    assert core.site_url(R("https://scarmenta.com")) == "https://scarmenta.com"
    assert core.site_url(R("https://scarmenta.com/")) == "https://scarmenta.com"
    assert core.site_url(R("https://evil.example")) == core.FRONTEND_URL
    assert core.site_url(R(None)) == core.FRONTEND_URL


def test_single_admin_in_db():
    db = MongoClient("mongodb://localhost:27017")["test_database"]
    assert db.users.count_documents({"role": "admin"}) == 1
