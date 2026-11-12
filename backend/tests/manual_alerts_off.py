# Manual check: with deposit_alerts OFF a demo deposit triggers no email send; restores the setting and rejects the deposit
import os, time, uuid, subprocess, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
o = requests.Session(); o.post(f"{API}/auth/login", json={"email": "admin@aetheria.io", "password": "Admin@12345"})
d = requests.Session(); d.post(f"{API}/auth/login", json={"email": "demo@aetheria.io", "password": "Demo@12345"})
s = o.get(f"{API}/admin/settings").json()
print("orig", s["deposit_alerts"], o.put(f"{API}/admin/settings", json={**s, "deposit_alerts": False}).status_code)
before = int(subprocess.check_output("grep -c 'email/send' /var/log/supervisor/backend.err.log || true", shell=True) or 0)
ref = "TESTOFF" + uuid.uuid4().hex[:8]
r = d.post(f"{API}/deposits", json={"amount": 100, "method": "usdt", "network": "TRC20", "payment_reference": ref})
print("deposit", r.status_code)
time.sleep(4)
after = int(subprocess.check_output("grep -c 'email/send' /var/log/supervisor/backend.err.log || true", shell=True) or 0)
print("email sends during OFF:", after - before)
print("reject", o.post(f"{API}/admin/deposits/{r.json()['id']}/reject", json={"reason": "TEST"}).status_code)
print("restore", o.put(f"{API}/admin/settings", json={**s, "deposit_alerts": s["deposit_alerts"]}).status_code,
      o.get(f"{API}/admin/settings").json()["deposit_alerts"])
import pymongo; pymongo.MongoClient("mongodb://localhost:27017")["test_database"].deposits.delete_one({"id": r.json()["id"]})
