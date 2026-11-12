import json
import logging
import os
import re
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Literal, Optional

from pydantic import BaseModel, Field
from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage

from agents import TIER_TEXT, _stats, tier_rate
from core import db, get_current_user, require_admin, require_staff, get_settings, new_id, new_ticket, now, now_iso

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
MODEL = ("openai", "gpt-6-luna")
HISTORY_LIMIT = 30
RATE_LIMIT = 20
RATE_WINDOW_MIN = 10
MAX_ANSWERS = 60
SESSION_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
TICKET_RE = re.compile(r"\[\[\s*TICKET:\s*(.+?)\s*\|\s*(\w+)\s*\]\]", re.S)
CATEGORIES = {"deposit", "wallet", "account", "technical", "other"}


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
- Agents earn tiered commission on their referred players' approved deposits: 1-10 players 5%, 11-50 players 7%, 51+ players 10%. Agents see players, commissions and payouts in the Agent Portal; payouts are made by Scarmenta admin.
- Login with email + password or a 6-digit email code (OTP). Forgot password link is on the login page.
- Scarmenta does NOT guarantee profits, winnings or daily earnings. The compound calculator is only a math example.
- Player dashboard pages: Overview, Deposits, Transfer, Games, Calculator, Refer & Earn, Loss Rewards, Statement, Support, My Account. Agent portal pages: Dashboard, Support, My Account."""


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


async def agent_snapshot(agent: dict) -> str:
    st = (await _stats([agent["id"]]))[agent["id"]]
    return f"""This agent's account (private to them; share only with them):
- Name: {agent.get('name')}, agent code: {agent.get('agent_code') or '-'}, signup link uses ?agent=<code>
- Referred players: {st['players']}, current commission rate: {tier_rate(st['players']):g}% ({TIER_TEXT})
- Player deposit volume: ${st['volume']:,.2f}; commission earned: ${st['earned']:,.2f}; unpaid: ${st['unpaid']:,.2f}; paid out: ${st['paid']:,.2f}"""


TICKET_RULE = """If you cannot resolve the issue yourself (deposit not credited, refunds, disputes, locked account, bugs, anything needing staff), or the user asks for a human, tell them in one sentence that you are opening a support ticket for them, then end your reply with exactly this tag on its own line:
[[TICKET: <short subject in English, max 80 chars> | <one of: deposit, wallet, account, technical, other>]]
Use the tag only when really needed, never for questions you answered."""


async def official_answers() -> str:
    docs = await db.bot_answers.find({"active": True, "deleted": {"$ne": True}}, {"_id": 0, "question": 1, "answer": 1}
                                     ).sort("created_at", 1).to_list(MAX_ANSWERS)
    if not docs:
        return ""
    items = "\n".join(f"Q: {d['question']}\nA: {d['answer']}" for d in docs)
    return f"""OFFICIAL ANSWERS written by Scarmenta admin. When the user's question matches one of these (in any language or wording), reply with that answer: keep its meaning, facts, numbers and links exactly; only translate it into the user's language and adjust grammar. These override the general facts below.
{items}

"""


async def system_prompt(user: dict) -> str:
    snapshot = await (agent_snapshot(user) if user["role"] == "agent" else account_snapshot(user))
    where = "agent portal" if user["role"] == "agent" else "player dashboard"
    return f"""You are Scara, the friendly Scarmenta help assistant inside the {where}.
Answer briefly (2-6 short sentences or a short list). Plain text only, no markdown symbols like ** or #. Reply in the same language the user writes in (Hindi, Hinglish, English, etc.).
Never promise profits or returns. Never say withdrawals are possible. Never ask for passwords, OTP codes or payment PINs.
You cannot change balances, approve deposits or perform actions; explain which page to use instead.

{TICKET_RULE}

{await official_answers()}{platform_facts(await get_settings())}

{snapshot}"""


async def ticket_from_chat(user: dict, session_id: str, m: re.Match, past: list, text: str) -> dict:
    existing = await db.tickets.find_one({"chat_session_id": session_id, "user_id": user["id"], "status": {"$ne": "closed"}},
                                         {"_id": 0, "reference": 1})
    if existing:
        return existing
    lines = [f"{'Me' if x['role'] == 'user' else 'Scara (AI)'}: {x['content']}" for x in reversed(past[:10])]
    transcript = "\n".join([*lines, f"Me: {text}"])[-1900:]
    category = m.group(2).lower() if m.group(2).lower() in CATEGORIES else "other"
    subject = (m.group(1).strip() or "Help requested via chat")[:110]
    t = new_ticket(user, subject, category, f"Opened by the AI assistant. Chat so far:\n{transcript}",
                   chat_session_id=session_id, source="assistant")
    t["messages"][0]["author_name"] = f"Scara AI (for {user['name']})"
    await db.tickets.insert_one(dict(t))
    return t


@router.get("/assistant/history")
async def history(session_id: str = Query(min_length=8, max_length=64), user: dict = Depends(get_current_user)):
    msgs = await db.chat_messages.find({"user_id": user["id"], "session_id": session_id},
                                       {"_id": 0, "id": 1, "role": 1, "content": 1, "rating": 1, "created_at": 1}).sort("created_at", 1).to_list(200)
    return msgs


class RateIn(BaseModel):
    rating: Literal["up", "down"]
    reason: Optional[str] = Field(default=None, max_length=300)


@router.post("/assistant/messages/{mid}/rate")
async def rate_message(mid: str, body: RateIn, user: dict = Depends(get_current_user)):
    reason = (body.reason or "").strip() or None if body.rating == "down" else None
    r = await db.chat_messages.update_one({"id": mid, "user_id": user["id"], "role": "assistant"},
                                          {"$set": {"rating": body.rating, "rating_reason": reason, "rated_at": now_iso()}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"ok": True}


class AnswerIn(BaseModel):
    question: str = Field(min_length=3, max_length=200)
    answer: str = Field(min_length=3, max_length=1500)
    active: bool = True


class AnswerPatch(BaseModel):
    question: Optional[str] = Field(default=None, min_length=3, max_length=200)
    answer: Optional[str] = Field(default=None, min_length=3, max_length=1500)
    active: Optional[bool] = None


ANSWER_FIELDS = {"_id": 0, "id": 1, "question": 1, "answer": 1, "active": 1, "created_at": 1, "updated_at": 1}


@router.get("/admin/assistant/answers")
async def list_answers(_: dict = Depends(require_staff)):
    return await db.bot_answers.find({"deleted": {"$ne": True}}, ANSWER_FIELDS).sort("created_at", -1).to_list(MAX_ANSWERS)


@router.post("/admin/assistant/answers")
async def create_answer(body: AnswerIn, admin: dict = Depends(require_admin)):
    if await db.bot_answers.count_documents({"deleted": {"$ne": True}}) >= MAX_ANSWERS:
        raise HTTPException(status_code=400, detail=f"You can save up to {MAX_ANSWERS} answers")
    doc = {"id": new_id(), "question": body.question.strip(), "answer": body.answer.strip(), "active": body.active,
           "created_by": admin["email"], "created_at": now_iso(), "updated_at": now_iso(), "deleted": False}
    await db.bot_answers.insert_one(dict(doc))
    return {k: doc[k] for k in ANSWER_FIELDS if k != "_id"}


@router.patch("/admin/assistant/answers/{aid}")
async def update_answer(aid: str, body: AnswerPatch, _: dict = Depends(require_admin)):
    data = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump(exclude_none=True).items()}
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")
    r = await db.bot_answers.update_one({"id": aid, "deleted": {"$ne": True}}, {"$set": {**data, "updated_at": now_iso()}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Answer not found")
    return {"ok": True}


@router.delete("/admin/assistant/answers/{aid}")
async def delete_answer(aid: str, _: dict = Depends(require_admin)):
    r = await db.bot_answers.update_one({"id": aid}, {"$set": {"deleted": True, "active": False}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Answer not found")
    return {"ok": True}


@router.post("/assistant/chat")
async def chat(body: ChatIn, user: dict = Depends(get_current_user)):
    if user["role"] not in ("user", "agent"):
        raise HTTPException(status_code=403, detail="The assistant is available for players and agents only")
    if not SESSION_RE.match(body.session_id):
        raise HTTPException(status_code=400, detail="Invalid session")
    since = (now() - timedelta(minutes=RATE_WINDOW_MIN)).isoformat()
    if await db.chat_messages.count_documents({"user_id": user["id"], "role": "user", "created_at": {"$gt": since}}) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="You're sending messages too fast. Please wait a few minutes.")
    past = await db.chat_messages.find({"user_id": user["id"], "session_id": body.session_id},
                                       {"_id": 0, "role": 1, "content": 1}).sort("created_at", -1).to_list(HISTORY_LIMIT)
    llm = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=body.session_id, system_message="",
                  initial_messages=[{"role": "system", "content": await system_prompt(user)}, *reversed(past)]
                  ).with_model(*MODEL)
    text = body.message.strip()
    asked_at = now_iso()

    async def events():
        reply, sent = "", 0
        try:
            async for ev in llm.stream_message(UserMessage(text=text)):
                if isinstance(ev, TextDelta):
                    reply += ev.content
                    cut = reply.find("[[")
                    head = reply[:cut] if cut >= 0 else reply[:len(reply) - (1 if reply.endswith("[") else 0)]
                    safe = len(head.rstrip())
                    if safe > sent:
                        yield f"data: {json.dumps({'delta': reply[sent:safe]})}\n\n"
                        sent = safe
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:
            logger.error(f"assistant stream failed: {e}")
            yield f"data: {json.dumps({'error': 'The assistant is busy right now. Please try again in a moment.'})}\n\n"
        m, cut = TICKET_RE.search(reply), reply.find("[[")
        if cut >= 0:
            reply = reply[:cut].rstrip()
        elif len(reply) > sent:
            yield f"data: {json.dumps({'delta': reply[sent:]})}\n\n"
        if not reply:
            yield "data: [DONE]\n\n"
            return
        if m:
            ticket = await ticket_from_chat(user, body.session_id, m, past, text)
            note = f"\n\nSupport ticket {ticket['reference']} is open. Our team will reply on the Support page."
            reply += note
            yield f"data: {json.dumps({'delta': note, 'ticket': {'reference': ticket['reference']}})}\n\n"
        await db.chat_messages.insert_one({"id": new_id(), "user_id": user["id"], "session_id": body.session_id,
                                           "role": "user", "content": text, "created_at": asked_at})
        mid = new_id()
        await db.chat_messages.insert_one({"id": mid, "user_id": user["id"], "session_id": body.session_id,
                                           "role": "assistant", "content": reply, "question": text, "created_at": now_iso()})
        yield f"data: {json.dumps({'message_id': mid})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


STOP = set("""a an the and or but if then so to of in on at for from by with about as is are was were be been am i me my
you your we our it its this that these those what which who whom how why when where can could would should will do does did
have has had not no yes please hi hello hey ok okay thanks thank kya hai hain ho hoga kaise kaisa kab kahan kyu kyun mera meri
mere mujhe main mai hum aap ap tum ka ki ke ko se me mein par pe aur ya bhi nahi na toh to tha thi the kar karna karu karo
karein kuch koi ek bata batao btao sakta sakte sakti raha rahi rahe chahiye wala wali wale abhi gaya gayi karni
kisi hoon baat maine poocha kitni kitna kitne kab tak liye sab work want need help get never ago got many
much days day still yet already just also any some very really more most one two three din""".split())


@router.get("/admin/assistant/insights")
async def insights(days: int = Query(default=30, ge=1, le=365), _: dict = Depends(require_staff)):
    since = (now() - timedelta(days=days)).isoformat()
    qs = await db.chat_messages.find({"role": "user", "created_at": {"$gt": since}},
                                     {"_id": 0, "content": 1, "user_id": 1, "session_id": 1, "created_at": 1}
                                     ).sort("created_at", -1).to_list(5000)
    words, repeats = Counter(), Counter()
    for q in qs:
        norm = " ".join(re.findall(r"[\w']+", q["content"].lower()))
        repeats[norm] += 1
        words.update({w for w in norm.split() if len(w) > 2 and w not in STOP and not any(ch.isdigit() for ch in w)})
    users = {u["id"]: u for u in await db.users.find({"id": {"$in": list({q["user_id"] for q in qs})}},
                                                     {"_id": 0, "id": 1, "name": 1, "role": 1}).to_list(5000)}
    rated = await db.chat_messages.find({"role": "assistant", "rating": {"$in": ["up", "down"]}, "rated_at": {"$gt": since}},
                                        {"_id": 0, "user_id": 1, "rating": 1, "rating_reason": 1, "question": 1,
                                         "content": 1, "rated_at": 1}).sort("rated_at", -1).to_list(2000)
    downs = [r for r in rated if r["rating"] == "down"]
    users.update({u["id"]: u for u in await db.users.find({"id": {"$in": list({r["user_id"] for r in downs[:30]} - set(users))}},
                                                          {"_id": 0, "id": 1, "name": 1, "role": 1}).to_list(100)})
    return {
        "ratings": {"up": len(rated) - len(downs), "down": len(downs)},
        "disliked": [{"question": r.get("question") or "—", "answer": r["content"], "reason": r.get("rating_reason"),
                      "name": users.get(r["user_id"], {}).get("name", "—"), "rated_at": r["rated_at"]} for r in downs[:30]],
        "days": days, "questions": len(qs), "people": len({q["user_id"] for q in qs}),
        "chats": len({q["session_id"] for q in qs}),
        "tickets": await db.tickets.count_documents({"source": "assistant", "created_at": {"$gt": since}}),
        "top_words": [{"word": w, "count": c} for w, c in words.most_common(25)],
        "top_questions": [{"question": q, "count": c} for q, c in repeats.most_common(10) if c > 1],
        "recent": [{"question": q["content"], "created_at": q["created_at"],
                    "name": users.get(q["user_id"], {}).get("name", "—"), "role": users.get(q["user_id"], {}).get("role", "user")}
                   for q in qs[:50]],
    }
