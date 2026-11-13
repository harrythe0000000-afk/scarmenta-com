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

## 2026-11-12 Demo games v2
- Demo page now tabs: Scarmenta vs Rivals, Andar Bahar (Andar 0.9:1, Bahar 1:1, joker + alternate deal, Andar first), Tutorial (2x 3-step guides)
- Web Audio synthesized sounds (flip/chip/win/lose), on by default, mute persisted (scarmenta_demo_sound)
- "Ready for real play?" dialog after 5 total rounds -> /app/deposits
- Shared demo balance $1,000 per page open + Reset. Tests: iteration_17.json (bugs fixed: AB winning-card highlight, mobile row order, toast position)

## 2026-11-12 Tutorial language + win streak
- Tutorial EN/Hinglish toggle (localStorage scarmenta_tutorial_lang)
- Win streak counter (net>0 rounds in a row, both tables) + best; "Hot Streak" badge + toast at 3

## 2026-11-12 Teen Patti demo, per-tab Hinglish, streak share, portfolio
- Teen Patti table (Rivals vs Scarmenta, 3 cards each, scan-line dealer effect, hand ranking lib/teenPatti.js, 1:1, tie push)
- Per-tab EN/Hinglish switch (lib/demoText.js, localStorage scarmenta_demo_langs)
- Session Portfolio bar (P/L, rounds, wins, losses, win rate, biggest win)
- Hot Streak share image (1080x1350, referral code + link, no demo note per user) via shareBlob (Web Share / download + api.whatsapp.com)
- Tests: iteration_18.json; fixed mobile tab overflow, small card text, WhatsApp emoji, Reset clears best

## 2026-11-12 Promo screenshot contest
- Players /app/contest: upload share screenshot (object storage, no limit), my entries status, winners gallery (masked)
- Admin/staff /admin/contest: pending/winners/rejected; admin enters bonus per winner -> promo_balance + tx contest_bonus (ref CON-xxxxxx); staff can reject only
- backend/contest.py; tests iteration_19.json pass

## 2026-11-12 Contest theme of the week
- Admin sets theme (title, message, banner image via /admin/banners/image, IST start/end) on /admin/contest; auto shows/hides by dates; latest live theme wins
- Player contest page shows ThemeBanner; entries tagged theme_title (shown to admin + player)
- API: GET /api/contest/theme, GET/POST/DELETE /api/admin/contest/themes

## 2026-11-12 Contest winner popup
- WinnerPopup (confetti, prize, winning screenshot, Share again -> /app/demo-game) shown once per win (winner_seen flag); before admin popups
- API: GET /api/contest/unseen-wins, POST /api/contest/entries/{id}/seen

## 2026-11-12 BULKAPI live casino (code complete, awaiting correct credentials)
- Doc: launch GET {BASE}/launch_game/?user_id,wallet_amount,game_uid,token,timestamp,payload(AES-256-ECB base64 of JSON, key=secret padded to 32). Callback POST form (mobile,bet_amount,win_amount,game_uid,game_round,token,...) -> return "ok"
- Doc says bulkapi.org but it has no DNS; bulkapi.site/launch_game/ responds -> BULKAPI_BASE_URL=https://bulkapi.site in backend/.env
- Real call result: {"status":"error","message":"Token not found or secret key missing in database."} -> stored BULKAPI_API_TOKEN is a URL (35 chars, wrong field), secret 30 chars (expected 32)
- backend/bulkapi.py: per-user 10-digit bulk_player_id, INR conversion via fx_rates.INR, callback token check (+ optional BULKAPI_CALLBACK_IPS), idempotent per game_round with delta updates, tx type live_round, GGR by provider
- Pages: /app/live-casino, /admin/live-casino (status, callback URL, games CRUD, GGR)
- Callback URL must be set in BULKAPI portal (single callback; currently Lara.in)

## 2026-11-13 BULKAPI backend rebuilt from GGR-integration-doc.pdf
- backend/bulkapi.py rewritten: launch GET bulkapi.site/launch_game/ (AES-256-ECB PKCS7 base64, PHP-style key pad), callback form/JSON, token check, idempotent per game_round (duplicate = update delta), returns "ok"
- Separate admin-editable live rate: db.settings {key:"live_casino", inr_rate} default 95; PUT /api/admin/live/rate
- POST /api/admin/live/test -> real launch call to BULKAPI, shows its reply. Admin LiveCasino page: Rate + Test cards
- Callback verified via curl (+$2 win, duplicate ignored, update applied delta). Live launch still fails: "Token not found or secret key missing" -> user skipped key card twice
- User chose: callback URL moves to https://scarmenta.com/api/bulkapi/callback (Lara.in will stop); Scarmenta prod IP must be whitelisted at BULKAPI
- Pending (user deferred): Scarmenta vs Others rigged odds + 50% profit message

## 2026-11-13 GGR Live Casino full integration (iteration_20)
- Launch: BULKAPI_BASE_URL=https://bulkapi.org (user chose .org only; .org has NO DNS right now -> launches fail until provider fixes it; bulkapi.site works as same system)
- Callbacks: /api/bulkapi/callback AND /api/game_callback.php (form or JSON). Token check, optional IP whitelist BULKAPI_CALLBACK_IPS, non-finite amounts rejected, round owner check (409), 2-decimal USD deltas, settled flag
- Collections: live_sessions (launch history incl failed), live_rounds, live_callbacks (every callback, failed flag)
- Admin tabs: Setup & games, Launch history, Bets & wins, Player report, Callback logs (components/LiveReports.jsx)
- Keys BULKAPI_API_TOKEN/SECRET_KEY injected via process env (not in .env file); current values invalid (secret 30 bytes)

## 2026-11-13 Admin-panel BULKAPI keys + bulk game import (iteration_21)
- PUT/DELETE /api/admin/live/credentials: Fernet-encrypted (key = sha256(JWT_SECRET)) in db.settings {key:"bulkapi_creds"}; falls back to env keys; 30s cache; masked in status (source shown); rejects URL-looking token
- POST /api/admin/live/games/import (.csv/.xlsx via openpyxl; headers name, provider, game_uid + aliases; duplicates skipped)
- Current server env token is actually a URL ending .php (callback URL pasted by mistake) and secret is 30 chars -> user must paste real keys in Admin > Live Casino > BULKAPI keys
- Still pending: real game_uid list from provider, bulkapi.org DNS, Lara callback -> https://scarmenta.com/api/game_callback.php

## 2026-11-13 Live casino player filters + default photos
- Player page: provider buttons + search box; games without image use AI default photo by name keyword (roulette/blackjack/baccarat/teen patti/andar bahar/dragon tiger/dice) else by provider (lib/liveImages.js)
- 2026-11-13: GET /api/live/popular (all-time round counts, top 5 active games); 'Most played' row with rank badges on player page, hidden while filtering
- 2026-11-13: Favourites: users.live_favourites; GET /api/live/favourites, PUT /api/live/favourites/{id} {favourite}; heart on each tile + 'Favourites (n)' filter button
- 2026-11-13: Recently played row (GET /api/live/recent: user's last 5 distinct launched active games) above Most played, hidden while filtering

## 2026-11-13 Scarmenta vs Others demo rework (iteration_22, frontend only)
- Two demo wallets (Scarmenta credits 5000, Others ₹5000) in localStorage scarmenta_demo_rivals; refill via WhatsApp referral share or Deposit
- Bigger-bet side loses exactly 3 of every 5 rounds (lib/rivalsEngine.js); Repeat/Double bet; tie removed
- Result: Others win shows profit, credit cost (bet/promo_multiplier) and net; disclaimer states this table follows a practice pattern
- 2026-11-13: Hedge share card: totals (rounds, othersWins, othersProfit, creditCost, net) persisted in rivals state; 'Total net profit' bar + WhatsApp image (renderHedgeImage) with referral code, only when net > 0
- 2026-11-13: Demo share tracking: signup_source 'demo_share' (register ?src=demo&ref=CODE), share_visits.source; GET /api/admin/demo-shares {visits, signups, deposited, deposit_total}; card on Admin > Top sharers. demo_share signups do NOT get the calc share bonus
- 2026-11-13: Demo share bonus: settings.demo_share_bonus_amount (default 5, Admin Settings field), paid once per friend on first approved deposit via referrals.reward_share (generic by signup_source); admin demo-shares card shows bonuses paid; HedgeShare shows bonus hint
