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
