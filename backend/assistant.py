import json
import logging
import os
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage

from core import db, get_current_user, get_settings, new_id, now, now_iso

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
MODEL = ("openai", "gpt-6-luna")
HISTORY_LIMIT = 30
RATE_LIMIT = 20
RATE_WINDOW_MIN = 10
SESSION_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class ChatIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=2000)


def platform_facts(s: dict) -> str:
    return f"""Scarmenta facts (use only these; never invent numbers or policies):
- Users buy prepaid gaming credits in USD. Every approved cash deposit gives {s['promo_multiplier']:g}X credits (e.g. $50 -> ${50 * s['promo_multiplier']:g}).
- Deposit methods: USDT (TRC20/ERC20/BEP20) or UPI (INR). User pays, then submits the payment reference; staff verify and approve, then credits appear. Email must be verified before depositing.
- Min deposit ${s['min_deposit']:g}, max ${s['max_deposit']:g}. Packages: {', '.join(f'${p:g}' for p in s['packages'])}.
- NO WITHDRAWALS: credits are never withdrawable as cash. Credits are used on partner game platforms from the Games page.
- Transfers: credits can be sent to another Scarmenta user from the Transfer page with a {s['transfer_fee_percent']:g}% fee.
- Refer & Earn: {s['referral_bonus_percent']:g}% of friends' approved deposits. Loss rewards: {s['loss_reward_percent']:g}% of weekly net game losses, paid weekly.
- Agents earn tiered commission on referred players: 5% (1-10 referrals), 7% (10-50), 10% (over 50).
- Login with email + password or a 6-digit email code (OTP). Forgot password link is on the login page.
- Scarmenta does NOT guarantee profits, winnings or daily earnings. The compound calculator is only a math example.
- Pages in the player dashboard: Overview, Deposits, Transfer, Games, Calculator, Refer & Earn, Loss Rewards, Statement, Support, My Account.
- Anything you can't resolve (payment disputes, refunds, account problems): tell the user to open a ticket on the Support page."""


async def account_snapshot(user: dict) -> str:
    agg = await db.deposits.aggregate([
        {"$match": {"user_id": user["id"]}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}, "amt": {"$sum": "$amount"}}}]).to_list(10)
    by = {a["_id"]: a for a in agg}
    recent = await db.deposits.find({"user_id": user["id"]}, {"_id": 0, "amount": 1, "status": 1, "created_at": 1}) \
        .sort("created_at", -1).to_list(5)
    rec = "; ".join(f"${d['amount']:g} {d['status']} on {d['created_at'][:10]}" for d in recent) or "none"
    return f"""This user's account (private to them; share only with them):
- Name: {user.get('name')}, email verified: {'yes' if user.get('email_verified') else 'no'}
- Credit balance: ${user.get('promo_balance', 0):,.2f}
- Approved deposits: {by.get('approved', {}).get('n', 0)} totalling ${by.get('approved', {}).get('amt', 0):,.2f}; pending: {by.get('pending', {}).get('n', 0)}; rejected: {by.get('rejected', {}).get('n', 0)}
- Recent deposits: {rec}
- Referral code: {user.get('referral_code') or '-'}, referral earnings: ${user.get('referral_earnings', 0):,.2f}, loss rewards received: ${user.get('loss_rewards_total', 0):,.2f}"""


async def system_prompt(user: dict) -> str:
    return f"""You are Scara, the friendly Scarmenta help assistant inside the player dashboard.
Answer briefly (2-6 short sentences or a short list). Plain text only, no markdown symbols like ** or #. Reply in the same language the user writes in (Hindi, Hinglish, English, etc.).
Never promise profits or returns. Never say withdrawals are possible. Never ask for passwords, OTP codes or payment PINs.
You cannot change balances, approve deposits or perform actions; explain which page to use instead.

{platform_facts(await get_settings())}

{await account_snapshot(user)}"""


@router.get("/assistant/history")
async def history(session_id: str = Query(min_length=8, max_length=64), user: dict = Depends(get_current_user)):
    msgs = await db.chat_messages.find({"user_id": user["id"], "session_id": session_id},
                                       {"_id": 0, "role": 1, "content": 1, "created_at": 1}).sort("created_at", 1).to_list(200)
    return msgs


@router.post("/assistant/chat")
async def chat(body: ChatIn, user: dict = Depends(get_current_user)):
    if user["role"] != "user":
        raise HTTPException(status_code=403, detail="The assistant is available for players only")
    if not SESSION_RE.match(body.session_id):
        raise HTTPException(status_code=400, detail="Invalid session")
    past = await db.chat_messages.find({"user_id": user["id"], "session_id": body.session_id},
                                       {"_id": 0, "role": 1, "content": 1}).sort("created_at", -1).to_list(HISTORY_LIMIT)
    llm = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=body.session_id, system_message="",
                  initial_messages=[{"role": "system", "content": await system_prompt(user)}, *reversed(past)]
                  ).with_model(*MODEL)
    since = (now() - timedelta(minutes=RATE_WINDOW_MIN)).isoformat()
    if await db.chat_messages.count_documents({"user_id": user["id"], "role": "user", "created_at": {"$gt": since}}) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="You're sending messages too fast. Please wait a few minutes.")
    text = body.message.strip()
    asked_at = now_iso()

    async def events():
        reply = ""
        try:
            async for ev in llm.stream_message(UserMessage(text=text)):
                if isinstance(ev, TextDelta):
                    reply += ev.content
                    yield f"data: {json.dumps({'delta': ev.content})}\n\n"
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:
            logger.error(f"assistant stream failed: {e}")
            yield f"data: {json.dumps({'error': 'The assistant is busy right now. Please try again in a moment.'})}\n\n"
        if reply:
            await db.chat_messages.insert_one({"id": new_id(), "user_id": user["id"], "session_id": body.session_id,
                                               "role": "user", "content": text, "created_at": asked_at})
            await db.chat_messages.insert_one({"id": new_id(), "user_id": user["id"], "session_id": body.session_id,
                                               "role": "assistant", "content": reply, "created_at": now_iso()})
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
