# Helper: seed/clean TEST live_events + big-win round for popup/feed UI tests.
# usage: python manual_live_popup_seed.py event <bet> <win> | bigwin | clean
import sys, uuid, pymongo
from datetime import datetime, timezone
db = pymongo.MongoClient("mongodb://localhost:27017")["test_database"]
uid = db.users.find_one({"email": "demo@aetheria.io"})["id"]
cmd = sys.argv[1]
now = datetime.now(timezone.utc).isoformat()
if cmd == "event":
    bet, win = float(sys.argv[2]), float(sys.argv[3])
    db.live_events.insert_one({"user_id": uid, "created_at": now, "bet_inr": bet, "win_inr": win,
                               "delta_usd": round((win - bet) / 95, 2), "event_key": f"TEST-EV-{uuid.uuid4()}"})
    print("event", now)
elif cmd == "bigwin":
    db.live_rounds.insert_one({"game_round": "TEST-BW-1", "user_id": uid, "game_name": "Lightning Roulette", "provider": "Evolution Live",
                               "bet_inr": 100, "win_inr": 1500, "net_inr": 1400, "updated_at": now, "settled": True})
    print("bigwin")
else:
    print(db.live_events.delete_many({"user_id": uid, "event_key": {"$regex": "^TEST-EV-"}}).deleted_count,
          db.live_rounds.delete_many({"user_id": uid, "game_round": "TEST-BW-1"}).deleted_count)
