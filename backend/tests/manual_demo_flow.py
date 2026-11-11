# One-off (not a pytest): demo referral flow (TEST referee with demo's code, $100 + $50 approved) and a demo
# bet $100 / win $20 on seeded provider "ezugi" (key rotated) so the UI loss-reward payout can be tested.
import os, uuid, json, requests
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env"); load_dotenv("/app/backend/.env")
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
adm = requests.Session(); adm.post(f"{API}/auth/login", json={"email": "admin@aetheria.io", "password": "Admin@12345"})
demo = requests.Session(); demo.post(f"{API}/auth/login", json={"email": "demo@aetheria.io", "password": "Demo@12345"})
before = demo.get(f"{API}/wallet").json()
code = demo.get(f"{API}/referrals/me").json()["code"]
es = requests.Session(); email = f"test_ref_{uuid.uuid4().hex[:6]}@example.com"
r = es.post(f"{API}/auth/register", json={"name": "TEST Referee", "email": email, "password": "Test@12345", "referral_code": code})
uid = r.json()["id"]; print("referee", email, uid, mongo.users.find_one({"id": uid})["referred_by_email"])
mongo.users.update_one({"id": uid}, {"$set": {"email_verified": True}})
for amt in (100, 50):
    d = es.post(f"{API}/deposits", json={"amount": amt, "method": "usdt", "network": "TRC20", "payment_reference": f"TESTREF{uuid.uuid4().hex[:8]}"}).json()
    print("approve", amt, adm.post(f"{API}/admin/deposits/{d['id']}/approve").status_code)
after = demo.get(f"{API}/wallet").json()
print("demo before", before, "\ndemo after", after)
print([(t["type"], t["amount"]) for t in demo.get(f"{API}/transactions", params={"type": "referral_bonus"}).json()])
# game activity on demo
ez = [p for p in adm.get(f"{API}/admin/providers").json() if p["code"] == "ezugi"][0]
key = adm.post(f"{API}/admin/providers/{ez['id']}/rotate-key").json()["api_key"]
tok = demo.post(f"{API}/games/launch", json={"provider_id": ez["id"]}).json()["session_token"]
H = {"X-Provider-Key": key}
rid = f"TESTR{uuid.uuid4().hex[:6]}"
print(requests.post(f"{API}/provider/v1/bet", headers=H, json={"session_token": tok, "transaction_id": rid + "b", "round_id": rid, "amount": 100}).json())
print(requests.post(f"{API}/provider/v1/win", headers=H, json={"session_token": tok, "transaction_id": rid + "w", "round_id": rid, "amount": 20}).json())
print("loss/me", {k: v for k, v in demo.get(f"{API}/rewards/loss/me").json().items() if k != "history"})
