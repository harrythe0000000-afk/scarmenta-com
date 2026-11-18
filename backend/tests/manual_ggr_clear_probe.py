# Manual (one real InfinityAPI probe): seeded GGR alert must be cleared by a successful provider test. usage: python manual_ggr_clear_probe.py <provider name>
import os, sys, requests, pymongo
from datetime import datetime, timezone
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
db = pymongo.MongoClient("mongodb://localhost:27017")["test_database"]
name = sys.argv[1] if len(sys.argv) > 1 else "JILI"
prov = db.live_providers.find_one({"name": name})
s = requests.Session()
s.post(f"{API}/auth/login", json={"email": "admin@aetheria.io", "password": "Admin@12345"})
db.settings.insert_one({"key": "infinity_ggr_alert", "message": "TEST_Provider GGR Balance is depleted", "at": datetime.now(timezone.utc).isoformat()})
print("before:", s.get(f"{API}/admin/live/ggr-alert").json())
r = s.post(f"{API}/admin/live/providers/{prov['id']}/test", json={"game_uid": ""})
print("test:", r.status_code, r.json().get("ok"), r.json().get("detail"))
print("after:", s.get(f"{API}/admin/live/ggr-alert").json())
after = db.live_providers.find_one({"id": prov["id"]})
print("enabled before/after:", prov.get("enabled"), after.get("enabled"))
if after.get("enabled") != prov.get("enabled"):
    db.live_providers.update_one({"id": prov["id"]}, {"$set": {"enabled": prov.get("enabled")}})
    print("restored enabled flag")
db.settings.delete_one({"key": "infinity_ggr_alert", "message": "TEST_Provider GGR Balance is depleted"})
