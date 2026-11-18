# Helper: send a test InfinityAPI callback for demo player, or clean up. usage: send <round> <bet> <win> | clean <round...>
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
import pymongo, requests
from dotenv import dotenv_values

FE, BE = dotenv_values("/app/frontend/.env"), dotenv_values("/app/backend/.env")
BASE = FE["REACT_APP_BACKEND_URL"].rstrip("/")
db = pymongo.MongoClient(BE["MONGO_URL"])[BE["DB_NAME"]]
demo = db.users.find_one({"email": "demo@aetheria.io"})
if sys.argv[1] == "send":
    s = requests.Session()
    s.post(f"{BASE}/api/auth/login", json={"email": "admin@aetheria.io", "password": "Admin@12345"})
    u = urlparse(s.get(f"{BASE}/api/admin/live/status").json()["callback_url"])
    rnd, bet, win = sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    r = requests.post(f"{BASE}{u.path}?token={parse_qs(u.query)['token'][0]}", json={
        "member_account": f"scm_{demo['bulk_player_id']}", "game_uid": "9418", "game_round": rnd, "serial_number": f"S-{rnd}",
        "bet_amount": bet, "win_amount": win, "timestamp": datetime.now(timezone.utc).isoformat()})
    print(r.status_code, r.text)
else:
    for rnd in sys.argv[2:]:
        ev = list(db.live_events.find({"user_id": demo["id"], "game_round": rnd}))
        for e in ev:
            db.transactions.delete_many({"user_id": demo["id"], "type": "live_round", "reference": f"LIVE-{e['event_key'][:16]}"})
        db.live_events.delete_many({"user_id": demo["id"], "game_round": rnd})
        db.live_rounds.delete_many({"user_id": demo["id"], "game_round": {"$regex": f":{rnd}:"}})
        db.live_callbacks.delete_many({"game_round": rnd})
    db.users.update_one({"id": demo["id"]}, {"$set": {"promo_balance": 1039}})
    print("cleaned")
