# Aetheria Credit OS — PRD

## Original problem
Gaming Technology & Credit Management Platform (Cyprus HQ; South Asia & Middle East). Prepaid credit packages (₹20,000 → ₹1,00,000 promo, 5X), fixed 20% tech service fee, separate real-money and promo wallets. User dashboard + Admin dashboard, transparent accounting, no manipulation of third-party outcomes. Luxury dark black/purple fintech UI.

## User choices
- Gaming provider integration: SKIPPED for now
- Payment gateway: MOCK (simulated; deposits pending → admin approves)
- Stack: FastAPI + MongoDB + React
- Auth: email + password (JWT httpOnly cookies)
- KYC: email verification only (Emergent-managed Resend sends real emails)

## Credit model (implemented)
Deposit D → fee = D × fee% (default 20) → real wallet += D − fee; promo wallet += D × multiplier (default 5). 3 ledger entries per approved deposit (deposit, service_fee, promo_credit). Admin can change fee/multiplier (applies to new deposits).

## Implemented (Nov 2026)
- Landing page with live calculator, packages, compliance section
- Auth: register/login/logout/refresh/me, email verification + resend, forgot/reset password, brute-force lockout (5 fails/email → 15 min + fraud alert)
- User: wallets overview, packages, mock deposit dialog (UPI/NetBanking/Card/AED wire/USDT), deposit history, statement (filters, CSV, print), support tickets
- Admin: cockpit stats + 30-day charts, deposit approval queue (approve/reject, risk score), users (search, suspend/activate, balance adjust w/ ledger), platform ledger, fraud alerts (high amount, velocity, login lockout), ticket inbox, fee/multiplier/limits/packages/fraud-rule config
- Seed: admin + verified demo player (see test_credentials.md)

## Backlog
- P1: Gaming provider integration layer (Evolution/Ezugi/Pragmatic) when contracts exist; real payment gateway
- RULE (user, Nov 2026): NO withdrawals — prepaid credits are non-withdrawable/non-refundable (disclosed on landing, wallets, deposit dialog)
- P1: KYC document upload + review; 2FA
- P2: Multi-currency (AED/USDT) wallets; scheduled monthly statements by email; refresh-token rotation/revocation; Mongo transactions for ledger atomicity; shadcn date picker

## Update (Nov 2026) — USD + rewards + game wallet API
- Currency: everything in USD. Deposits: USDT (TRC20/ERC20/BEP20, all countries) or UPI (INR at admin-set rate, default $1=₹95). User submits UTR/TX hash; admin verifies & approves. Payment refs unique (case-insensitive).
- 5X credit into one main balance; no fees; NO withdrawals.
- Refer & earn: 10% (configurable) of EVERY approved deposit by referred friend → referrer main balance; tracked as referral_earnings (separate column/cards).
- Weekly loss rewards: admin pays % (default 5) of net loss (bets − refunds − wins) per period; non-overlapping periods, locked payout.
- Game providers: Evolution / Ezugi / Pragmatic seeded as slots (no launch URL yet). Seamless wallet API /api/provider/v1/{balance,bet,win,rollback} with X-Provider-Key; idempotent.
- Admin: Money Flow page, Loss Rewards, Referrals, Game Providers, Game Activity, Credit Config (multiplier, packages, fx rates, UPI/USDT addresses, referral %, loss %).
## Backlog
- P1: Real provider contracts → set launch URLs + hand over keys; change-password / multiple admin accounts; per-game catalog
- P2: Auto-verify USDT via blockchain explorer; scheduled weekly loss-reward run; shadcn date picker

## Update — Brand Scarmenta + account settings + OTP
- Brand renamed to Scarmenta; AI-generated manta-ray logo at /frontend/public/scarmenta-logo.png (+ favicon.png); gold accent (#F2B94B) added from the logo.
- Email OTP login (6-digit, 10 min, 5 attempts, 60s resend limit).
- PUT /api/auth/account: change name / login email / password (current password required, 5-try lock). Admin page /admin/account.
- Seed creates the admin only if NO admin exists (so a changed admin email is never re-created from env).
- Not built: "potential earning" package claims and the opposite-betting homepage section (misleading); Stripe (does not allow gambling businesses).

## Update — Transfers, agent tiers, deposit alerts, agents
- Deposit alerts: background email to all active owner+staff on each new deposit (toggle deposit_alerts).
- Agents: role "agent", portal /agent, sign-up link ?agent=CODE, commission per approved deposit by tier (1–10 players 5%, 11–50 7%, 51+ 10%), owner records payouts.
- Account transfer: player → own other player account (proved by its password), fee transfer_fee_percent (default 5%), ledger transfer_out/transfer_in, /api/admin/transfers.
- Admin login links removed from /login and footer; admins use /admin (→ /admin/login) or /login.
- Declined (again): "potential earning up to 50%" package line — misleading for non-withdrawable credits.

## 2026-11-12 Terms & Conditions
- Signup par scrollable T&C box; poora scroll karne ke baad hi accept checkbox enable hota hai
- Public /terms page; content frontend/src/lib/terms.js me (effective 12 Nov 2026, support@scarmenta.com)
- Section 4 transfer line updated: transfers allowed only via official Transfer feature with 5% fee
- Backend /api/auth/register rejects accepted_terms=false; stores terms_accepted_at + terms_version on user

## 2026-11-12 Privacy Policy page
- Public /privacy page (content in frontend/src/lib/privacy.js) — PLACEHOLDER text until user sends real policy
- Linked from signup Terms checkbox, Terms sections 11 & 16, and /privacy links back to /terms

## 2026-11-12 Popups & Terms re-accept
- Admin page /admin/popups (owner only): upload image (Emergent object storage, backend/content.py), title, text, optional button (internal /path or https link), audience Players/Agents, preview, live toggle, soft delete
- Players/agents see active popups once per login (sessionStorage scarmenta_popups_seen cleared on login/logout)
- Admin "Ask all users to re-accept" sets settings.terms.reaccept_at; users with older terms_accepted_at get blocking scroll-to-accept dialog; stats accepted/pending
- Tests: backend/tests/test_popups_terms.py, test_reports/iteration_11.json (pass)

## 2026-11-12 Compound calculator + AI help chat
- /app/calculator: amount, daily %, period in days/weeks(7)/months(30)/years(365), presets, final/profit/growth, recharts area chart, milestone table, disclaimer, 3650-day cap, overflow handling
- AI chat "Scara" (backend/assistant.py, GPT 6 Luna gpt-6-luna via EMERGENT_LLM_KEY): floating widget for players only; SSE streaming; multi-turn sessions persisted in chat_messages (session id in localStorage, New chat button); knows platform facts + user account snapshot; 20 msgs / 10 min rate limit
- Popup stats (unique views/clicks) + IST scheduling added earlier today
- Tests: iteration_12.json, iteration_13.json pass

## 2026-11-12 Share image, chat handoff, agent chat, chat insights
- Calculator: Save image / Share on WhatsApp (canvas PNG 1080x1350 with result, chart, referral code + link, disclaimer; Web Share API on mobile, else download + wa.me)
- Bot auto-opens support ticket via [[TICKET: subject | category]] tag (stripped from stream); one open ticket per chat session; source=assistant, transcript included
- Agents: chat widget + bot knows agent stats/tier; new /agent/support page
- Admin/staff /admin/chat-insights: counts, top words (stopwords, no AI), repeated questions, latest 50; 7/30/90 days
- Tests: iteration_14.json pass

## 2026-11-12 Bot answers, chat ratings, share rewards
- /admin/bot-answers: admin CRUD (staff view) of official Q&A injected into Scara system prompt (max 60)
- Thumbs up/down on bot replies (+ optional reason on down); insights shows counts + disliked answers
- Share link ?ref=CODE&src=calc: visits (deduped per IP/24h), signups (signup_source=calc_share), deposited, earned; share_bonus_amount setting (default $5) paid once on friend first approved deposit (tx type share_bonus)
- Tests: iteration_15.json pass

## 2026-11-12 Weekly loss leaderboard
- /app/leaderboard (players only): top 10 by net game loss (bets - wins - rollbacks) over rolling last 7 days, global, masked names (De***o), own rank + estimated loss reward; GET /api/leaderboard/weekly in rewards.py
- Removed Cyprus / South Asia / Middle East mentions from landing, auth, statement

## 2026-11-12 Top sharers leaderboard
- Player Leaderboard tabs: Top losses / Top sharers (friends signed up via calc share link, rolling 7 days, masked)
- Admin /admin/top-sharers (admin only): full table, reward top 3 (default 25/15/10) -> promo_balance + tx sharer_reward; 7-day cooldown; db.locks guard against double pay
- Tests: iteration_16.json pass

## 2026-11-12 Demo card game + BULKAPI status
- /app/demo-game: frontend-only practice table "Scarmenta vs Rivals" (Stake/1win/4rabet text badges), higher card wins, same rank = Tie (8:1, side bets half back), fair crypto random, demo $1,000 balance reset on page open + Reset button; no backend, no real balance
- BULKAPI: paused by user. Report at memory/BULKAPI_REPORT.md. Secrets BULKAPI_API_TOKEN/SECRET_KEY/UNIQUE_CODE saved; no docs + shared callback with Lara.in blocks integration
