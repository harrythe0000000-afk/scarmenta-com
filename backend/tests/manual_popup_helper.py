# Helper: create/delete a TEST_ popup for UI regression with chat widget. usage: python manual_popup_helper.py create|delete <id>
import os, sys, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
s = requests.Session()
s.post(f"{API}/auth/login", json={"email": "admin@aetheria.io", "password": "Admin@12345"})
if sys.argv[1] == "create":
    r = s.post(f"{API}/admin/banners", json={"title": "TEST_ChatRegressionPopup", "text": "hello", "audience": ["user"]})
    print(r.status_code, r.json()["id"])
else:
    print(s.delete(f"{API}/admin/banners/{sys.argv[2]}").status_code)
