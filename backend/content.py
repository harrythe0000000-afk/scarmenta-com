import asyncio
import logging
import os
from typing import List, Literal, Optional

import io

import requests
from PIL import Image
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core import db, get_current_user, new_id, now_iso, require_admin

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "scarmenta"
MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
MAX_IMAGE = 5 * 1024 * 1024
_storage_key = None


def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key


def _storage_call(method: str, path: str, **kw):
    for attempt in (0, 1):
        r = requests.request(method, f"{STORAGE_URL}/objects/{path}",
                             headers={"X-Storage-Key": init_storage(force=attempt == 1), **kw.pop("headers", {})}, **kw)
        if r.status_code != 404 or attempt == 1:
            r.raise_for_status()
            return r


def put_object(path: str, data: bytes, content_type: str) -> dict:
    return _storage_call("PUT", path, headers={"Content-Type": content_type}, data=data, timeout=120).json()


def get_object(path: str) -> bytes:
    return _storage_call("GET", path, timeout=60).content


# ---------- Popup banners ----------
Audience = Literal["user", "agent"]


class BannerIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    text: str = Field(default="", max_length=1000)
    button_label: Optional[str] = Field(default=None, max_length=40)
    button_url: Optional[str] = Field(default=None, max_length=500)
    image_id: Optional[str] = None
    audience: List[Audience] = Field(min_length=1)
    active: bool = True


class BannerPatch(BaseModel):
    active: bool


def banner_out(b: dict) -> dict:
    return {k: b.get(k) for k in ("id", "title", "text", "button_label", "button_url", "image_id",
                                  "audience", "active", "created_at")}


@router.post("/admin/banners/image")
async def upload_banner_image(file: UploadFile = File(...), admin: dict = Depends(require_admin)):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in MIME:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP or GIF images are allowed")
    data = await file.read()
    if len(data) > MAX_IMAGE:
        raise HTTPException(status_code=400, detail="Image must be 5 MB or smaller")
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="This file is not a valid image")
    fid = new_id()
    try:
        res = await asyncio.to_thread(put_object, f"{APP_NAME}/banners/{fid}.{ext}", data, MIME[ext])
    except Exception as e:
        logger.error(f"Banner upload failed: {e}")
        raise HTTPException(status_code=502, detail="Image upload failed. Please try again.")
    await db.files.insert_one({"id": fid, "storage_path": res["path"], "original_filename": file.filename,
                               "content_type": MIME[ext], "size": len(data), "is_deleted": False,
                               "uploaded_by": admin["id"], "created_at": now_iso()})
    return {"image_id": fid}


@router.get("/banners/image/{fid}")
async def banner_image(fid: str):
    rec = await db.files.find_one({"id": fid, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Image not found")
    try:
        data = await asyncio.to_thread(get_object, rec["storage_path"])
    except Exception as e:
        logger.error(f"Banner image fetch failed: {e}")
        raise HTTPException(status_code=502, detail="Image temporarily unavailable")
    return Response(content=data, media_type=rec["content_type"], headers={"Cache-Control": "public, max-age=86400"})


@router.get("/admin/banners")
async def list_banners(admin: dict = Depends(require_admin)):
    docs = await db.banners.find({"deleted": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [banner_out(b) for b in docs]


@router.post("/admin/banners")
async def create_banner(body: BannerIn, admin: dict = Depends(require_admin)):
    if body.image_id and not await db.files.find_one({"id": body.image_id, "is_deleted": False}):
        raise HTTPException(status_code=400, detail="Uploaded image not found")
    if bool(body.button_label) != bool(body.button_url):
        raise HTTPException(status_code=400, detail="Button needs both a label and a link")
    url = body.button_url or ""
    if url and not (url.startswith(("https://", "http://")) or (url.startswith("/") and not url.startswith(("//", "/\\")))):
        raise HTTPException(status_code=400, detail="Button link must start with https:// or /")
    doc = {"id": new_id(), **body.model_dump(), "audience": sorted(set(body.audience)),
           "created_by": admin["email"], "created_at": now_iso(), "deleted": False}
    await db.banners.insert_one(dict(doc))
    return banner_out(doc)


@router.patch("/admin/banners/{bid}")
async def update_banner(bid: str, body: BannerPatch, admin: dict = Depends(require_admin)):
    r = await db.banners.update_one({"id": bid, "deleted": {"$ne": True}}, {"$set": {"active": body.active}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Popup not found")
    return {"ok": True}


@router.delete("/admin/banners/{bid}")
async def delete_banner(bid: str, admin: dict = Depends(require_admin)):
    r = await db.banners.update_one({"id": bid}, {"$set": {"deleted": True, "active": False}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Popup not found")
    return {"ok": True}


@router.get("/banners/active")
async def active_banners(user: dict = Depends(get_current_user)):
    if user["role"] not in ("user", "agent"):
        return []
    docs = await db.banners.find({"active": True, "deleted": {"$ne": True}, "audience": user["role"]},
                                 {"_id": 0}).sort("created_at", -1).to_list(20)
    return [banner_out(b) for b in docs]


# ---------- Terms re-acceptance ----------
class TermsAcceptIn(BaseModel):
    terms_version: str = Field(min_length=1, max_length=20)


async def terms_reaccept_at() -> Optional[str]:
    doc = await db.settings.find_one({"key": "terms"}, {"_id": 0})
    return (doc or {}).get("reaccept_at")


def needs_reaccept(user: dict, since: Optional[str]) -> bool:
    return bool(since) and (user.get("terms_accepted_at") or "") < since


@router.get("/terms/status")
async def terms_status(user: dict = Depends(get_current_user)):
    since = await terms_reaccept_at()
    return {"required": user["role"] in ("user", "agent") and needs_reaccept(user, since)}


@router.post("/terms/accept")
async def terms_accept(body: TermsAcceptIn, user: dict = Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": {"terms_accepted_at": now_iso(),
                                                            "terms_version": body.terms_version}})
    return {"ok": True}


@router.get("/admin/terms")
async def admin_terms(admin: dict = Depends(require_admin)):
    since = await terms_reaccept_at()
    q = {"role": {"$in": ["user", "agent"]}}
    total = await db.users.count_documents(q)
    pending = await db.users.count_documents(
        {**q, "$or": [{"terms_accepted_at": {"$exists": False}}, {"terms_accepted_at": None},
                      {"terms_accepted_at": {"$lt": since}}]}) if since else 0
    return {"reaccept_at": since, "total": total, "pending": pending, "accepted": total - pending}


@router.post("/admin/terms/require-reaccept")
async def require_reaccept(admin: dict = Depends(require_admin)):
    ts = now_iso()
    await db.settings.update_one({"key": "terms"}, {"$set": {"reaccept_at": ts, "set_by": admin["email"]}}, upsert=True)
    return {"reaccept_at": ts}
