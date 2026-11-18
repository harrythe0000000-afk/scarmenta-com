import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from bulkapi import LAUNCH_URL, probe
from core import db, new_id, now_iso, require_admin, require_staff

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
DEFAULTS = ["Evolution", "Ezugi", "Pragmatic", "JILI", "JDB", "SPRIBE"]
FIELDS = {"_id": 0}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40] or "provider"


async def ensure_providers(names, by: str = "system") -> None:
    for n in names:
        n = (n or "").strip()
        if len(n) < 2 or await db.live_providers.find_one({"name": n}, {"_id": 1}):
            continue
        pid = slug(n)
        if await db.live_providers.find_one({"provider_id": pid}, {"_id": 1}):
            pid = f"{pid}_{new_id()[:4]}"
        try:
            await db.live_providers.insert_one({"id": new_id(), "provider_id": pid, "name": n, "enabled": False,
                                                "last_test": None, "created_by": by, "created_at": now_iso()})
        except DuplicateKeyError:
            continue


async def seed_providers() -> None:
    r = await db.settings.update_one({"key": "live_providers_seeded"}, {"$setOnInsert": {"at": now_iso()}}, upsert=True)
    names = (DEFAULTS if r.upserted_id else []) + [p for p in await db.live_games.distinct("provider", {"deleted": {"$ne": True}}) if p]
    await ensure_providers(names)


class ProviderIn(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    provider_id: str = Field(default="", max_length=40)


class EnableIn(BaseModel):
    enabled: bool


class ProbeIn(BaseModel):
    game_uid: str = Field(default="", max_length=80)


@router.get("/admin/live/providers")
async def list_providers(_: dict = Depends(require_staff)):
    rows = await db.live_providers.find({}, FIELDS).sort("name", 1).to_list(500)
    counts = {c["_id"]: c["n"] for c in await db.live_games.aggregate([
        {"$match": {"deleted": {"$ne": True}}}, {"$group": {"_id": "$provider", "n": {"$sum": 1}}}]).to_list(500)}
    return [{**r, "endpoint": LAUNCH_URL, "games": counts.get(r["name"], 0)} for r in rows]


@router.post("/admin/live/providers")
async def add_provider(body: ProviderIn, admin: dict = Depends(require_admin)):
    name = body.name.strip()
    pid = slug(body.provider_id or name)
    if await db.live_providers.find_one({"$or": [{"name": name}, {"provider_id": pid}]}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="A provider with this name or ID already exists")
    doc = {"id": new_id(), "provider_id": pid, "name": name, "enabled": False, "last_test": None,
           "created_by": admin["email"], "created_at": now_iso()}
    await db.live_providers.insert_one(dict(doc))
    return {k: v for k, v in doc.items() if k != "_id"}


@router.post("/admin/live/providers/{pid}/test")
async def test_provider(pid: str, body: ProbeIn, admin: dict = Depends(require_admin)):
    prov = await db.live_providers.find_one({"id": pid}, FIELDS)
    if not prov:
        raise HTTPException(status_code=404, detail="Provider not found")
    uid = body.game_uid.strip()
    if not uid:
        game = await db.live_games.find_one({"provider": prov["name"], "deleted": {"$ne": True}, "broken": {"$ne": True}},
                                            {"_id": 0, "game_uid": 1}, sort=[("active", -1)])
        if not game:
            raise HTTPException(status_code=400, detail="Add at least one game for this provider before testing")
        uid = game["game_uid"]
    res = await probe(uid)
    test = {"ok": res["ok"], "status": res["status"], "game_uid": uid, "detail": res["detail"][:300],
            "by": admin["email"], "at": now_iso()}
    upd = {"last_test": test}
    if not res["ok"] and res["status"] and not res.get("game_missing") and "ggr" not in res["detail"].lower():
        upd["enabled"] = False
    await db.live_providers.update_one({"id": pid}, {"$set": upd})
    await db.live_provider_tests.insert_one({"id": new_id(), "provider": prov["name"], **test})
    logger.info(f"Provider test {prov['name']} uid={uid} ok={res['ok']}")
    return {**test, "redirect": res["redirect"]}


@router.patch("/admin/live/providers/{pid}")
async def toggle_provider(pid: str, body: EnableIn, admin: dict = Depends(require_admin)):
    prov = await db.live_providers.find_one({"id": pid}, FIELDS)
    if not prov:
        raise HTTPException(status_code=404, detail="Provider not found")
    if body.enabled and not (prov.get("last_test") or {}).get("ok"):
        raise HTTPException(status_code=400, detail="Run a successful test for this provider before turning it on")
    await db.live_providers.update_one({"id": pid}, {"$set": {"enabled": body.enabled, "updated_by": admin["email"],
                                                              "updated_at": now_iso()}})
    return {"ok": True}


@router.delete("/admin/live/providers/{pid}")
async def delete_provider(pid: str, _: dict = Depends(require_admin)):
    prov = await db.live_providers.find_one({"id": pid}, FIELDS)
    if not prov:
        raise HTTPException(status_code=404, detail="Provider not found")
    if await db.live_games.count_documents({"provider": prov["name"], "deleted": {"$ne": True}}):
        raise HTTPException(status_code=400, detail="Remove this provider's games first")
    await db.live_providers.delete_one({"id": pid})
    return {"ok": True}
