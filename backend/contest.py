import asyncio
import io
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from content import APP_NAME, MAX_IMAGE, MIME, get_object, put_object
from core import db, get_current_user, make_tx, new_id, now_iso, require_admin, require_staff
from rewards import _mask

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
TEAM = ("admin", "staff")


def entry_out(e: dict, full: bool = False) -> dict:
    keys = ["id", "caption", "status", "bonus", "created_at", "decided_at"]
    out = {k: e.get(k) for k in keys}
    out["name"] = e["user_name"] if full else _mask(e["user_name"])
    if full:
        out.update(user_email=e["user_email"], user_id=e["user_id"], note=e.get("note"))
    return out


@router.post("/contest/entries")
async def submit_entry(file: UploadFile = File(...), caption: Optional[str] = Form(default=None, max_length=200),
                       user: dict = Depends(get_current_user)):
    if user["role"] != "user":
        raise HTTPException(status_code=403, detail="Only players can join the contest")
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in MIME:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP or GIF screenshots are allowed")
    data = await file.read()
    if len(data) > MAX_IMAGE:
        raise HTTPException(status_code=400, detail="Screenshot must be 5 MB or smaller")
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="This file is not a valid image")
    eid = new_id()
    try:
        res = await asyncio.to_thread(put_object, f"{APP_NAME}/contest/{eid}.{ext}", data, MIME[ext])
    except Exception as e:
        logger.error(f"Contest upload failed: {e}")
        raise HTTPException(status_code=502, detail="Upload failed. Please try again.")
    doc = {"id": eid, "user_id": user["id"], "user_name": user["name"], "user_email": user["email"],
           "storage_path": res["path"], "content_type": MIME[ext], "caption": (caption or "").strip() or None,
           "status": "pending", "bonus": 0, "created_at": now_iso(), "decided_at": None}
    await db.contest_entries.insert_one(dict(doc))
    return entry_out(doc)


@router.get("/contest/me")
async def my_entries(user: dict = Depends(get_current_user)):
    docs = await db.contest_entries.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [entry_out(d) for d in docs]


@router.get("/contest/winners")
async def winners(_: dict = Depends(get_current_user)):
    docs = await db.contest_entries.find({"status": "winner"}, {"_id": 0}).sort("decided_at", -1).to_list(24)
    return [entry_out(d) for d in docs]


@router.get("/contest/image/{eid}")
async def entry_image(eid: str, user: dict = Depends(get_current_user)):
    e = await db.contest_entries.find_one({"id": eid}, {"_id": 0})
    if not e or not (e["status"] == "winner" or e["user_id"] == user["id"] or user["role"] in TEAM):
        raise HTTPException(status_code=404, detail="Image not found")
    try:
        data = await asyncio.to_thread(get_object, e["storage_path"])
    except Exception as ex:
        logger.error(f"Contest image fetch failed: {ex}")
        raise HTTPException(status_code=502, detail="Image temporarily unavailable")
    return Response(content=data, media_type=e["content_type"], headers={"Cache-Control": "private, max-age=3600"})


@router.get("/admin/contest/entries")
async def admin_entries(status: Literal["pending", "winner", "rejected"] = "pending",
                        _: dict = Depends(require_staff), limit: int = Query(default=200, le=500)):
    docs = await db.contest_entries.find({"status": status}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    counts = {s: await db.contest_entries.count_documents({"status": s}) for s in ("pending", "winner", "rejected")}
    return {"entries": [entry_out(d, full=True) for d in docs], "counts": counts}


class WinIn(BaseModel):
    amount: float = Field(gt=0, le=10000)


class RejectIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=200)


@router.post("/admin/contest/entries/{eid}/win")
async def pick_winner(eid: str, body: WinIn, admin: dict = Depends(require_admin)):
    amt = round(body.amount, 2)
    e = await db.contest_entries.find_one_and_update(
        {"id": eid, "status": "pending"},
        {"$set": {"status": "winner", "bonus": amt, "decided_at": now_iso(), "decided_by": admin["email"]}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not e:
        raise HTTPException(status_code=400, detail="This entry was already reviewed")
    u = await db.users.find_one_and_update({"id": e["user_id"]}, {"$inc": {"promo_balance": amt}},
                                           projection={"_id": 0, "password_hash": 0}, return_document=ReturnDocument.AFTER)
    if u:
        await db.transactions.insert_one(make_tx(u, "contest_bonus", "credit", amt, "Promo contest winner bonus",
                                                 f"CON-{eid[:6].upper()}", u["promo_balance"]))
    return entry_out(e, full=True)


@router.post("/admin/contest/entries/{eid}/reject")
async def reject_entry(eid: str, body: RejectIn, admin: dict = Depends(require_staff)):
    r = await db.contest_entries.update_one({"id": eid, "status": "pending"},
                                            {"$set": {"status": "rejected", "note": body.note, "decided_at": now_iso(),
                                                      "decided_by": admin["email"]}})
    if not r.matched_count:
        raise HTTPException(status_code=400, detail="This entry was already reviewed")
    return {"ok": True}
