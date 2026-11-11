# One-off helper: create a verified TEST user with a pending USDT deposit (for the admin approve UI test)
import os, uuid, requests
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env"); load_dotenv("/app/backend/.env")
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
s = requests.Session(); email = f"test_ui_{uuid.uuid4().hex[:6]}@example.com"
u = s.post(f"{API}/auth/register", json={"name": "TEST UiUser", "email": email, "password": "Test@12345"}).json()
mongo.users.update_one({"id": u["id"]}, {"$set": {"email_verified": True}})
d = s.post(f"{API}/deposits", json={"amount": 250, "method": "usdt", "network": "TRC20", "payment_reference": f"TESTTX{uuid.uuid4().hex[:10]}"}).json()
print(email, u["id"], d["reference"], d["payment_reference"])
