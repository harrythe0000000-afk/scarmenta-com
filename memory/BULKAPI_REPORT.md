# BULKAPI → Scarmenta Integration Report (Step 1 – Inspection)
Date: 12 Nov 2026 · Status: **NOT INTEGRATED — blocked on documentation and account setup**

## 1. What Scarmenta already has
- Seamless-wallet engine in `backend/games.py`: `POST /api/provider/v1/{balance,bet,win,rollback}`.
  - Auth: per-provider `X-Provider-Key` (sha256 hash stored, constant-time compare).
  - Idempotency: unique index `(provider_id, external_tx_id)` on `game_transactions`; duplicates return the cached reply.
  - Win requires a prior bet in the same round; rollback refunds the bet once.
  - Ledger: every bet/win/rollback is written to `game_transactions` and `transactions` (statement).
  - Player wallet = `users.promo_balance` (USD credits). Per-provider GGR stats are in `GET /api/admin/game-stats`.
- Game launch `POST /api/games/launch` creates a 4-hour session token, but **providers are placeholders (MOCK)**. There is no real launch URL, so no real game opens today.
- Missing for BULKAPI: an outbound launch client, a BULKAPI-format callback endpoint, signature or encryption verification, INR↔USD handling, a GGR wallet ledger and a game catalogue sync.

## 2. What we learned about BULKAPI (portal screenshot + public site)
| Item | Finding |
|---|---|
| Portal | bulkapi.site/brouser (account "laaara.in") |
| Credentials | API Token, Secret Key ("encrypts every game-launch request"), Unique Code |
| Callback URL | **One per account**, currently `https://laaara.in/vish/callback.php` |
| Domain | **One per account**: `https://laaara.in/` |
| Whitelisted server IPs | 89.117.157.170 (Lara.in server) |
| Currency | **INR** (Scarmenta credits are USD) |
| GGR wallet | Prepaid balance held at BULKAPI (≈ ₹2,43,504), so GGR is deducted from this deposit |
| Public docs | **None found.** Site has only marketing pages; tried /docs, /api, /documentation and similar, all 404 |
| Providers listed publicly | Evolution, Ezugi, Pragmatic, JILI, JDB, SPRIBE |
| Support contact | info@makaz.in · +91 9205629302 |

## 3. Provider availability (requested 7)
| Provider | Listed on bulkapi.site | Status |
|---|---|---|
| Ezugi | Yes | Needs confirmation of game list for this account |
| Evolution | Yes | Needs confirmation |
| Microgaming | Not listed | **Confirm with BULKAPI** |
| Playtech | Not listed | **Confirm with BULKAPI** |
| Iconic21 | Not listed | **Confirm with BULKAPI** |
| ORA Gaming | Not listed | **Confirm with BULKAPI** |
| Macro Gaming | Not listed | **Confirm with BULKAPI** |
The site says "one API integration", which suggests one credential set for all providers. This is **not verified**, so BULKAPI must confirm it.

## 4. Blocking issues
1. **Shared account conflict.** The account has one callback URL, one domain and one IP whitelist, all set to Lara.in. Pointing them at Scarmenta would **break Lara.in**.
   - Option A: BULKAPI gives Scarmenta its own sub-account or credentials. **Recommended.**
   - Option B: BULKAPI supports several callback URLs or domains per account.
   - Option C: Lara.in's callback forwards Scarmenta players to Scarmenta. This changes Lara.in, so it needs your approval.
2. **No API documentation.** We don't know the base URL, launch endpoint, request encryption (algorithm, key and IV), callback payload, signature method, response codes or game-list endpoint. Per your instruction, no endpoints will be invented.
3. **Currency.** The account is INR and Scarmenta is USD. We need to know whether the account can run in USD, or how conversion should work (the FX rate setting already exists).
4. **Whitelisting.** Scarmenta's production server IP must be added at BULKAPI. The deployer can find the outbound IP, but BULKAPI must add it.
5. **Security.** The API Token and Secret Key appeared in a screenshot shared in chat. **Ask BULKAPI to rotate the Secret Key** after setup.

## 5. Questions to send to BULKAPI (info@makaz.in)
1. Full API documentation (PDF or Postman): base URL, launch-game endpoint, encryption spec, callback payload samples (balance, bet, win, rollback/cancel), signature and verification, expected responses and error codes, retry policy, game-list endpoint.
2. Can Scarmenta get a separate sub-account (own callback, domain and IP whitelist) under the same commercial agreement and GGR wallet?
3. Which of Ezugi, Evolution, Microgaming, Playtech, Iconic21, ORA Gaming and Macro Gaming are enabled? Is one credential set enough for all of them? What are the GGR % rates?
4. Is USD supported? If not, what is the INR conversion policy?
5. Is there a sandbox or test mode for checking callbacks?
6. What source IP(s) do BULKAPI callbacks come from, so we can whitelist them on our side?

## 6. Implementation plan (starts once docs and a separate account are available)
1. Secrets: BULKAPI_API_TOKEN, BULKAPI_SECRET_KEY, BULKAPI_UNIQUE_CODE, plus BULKAPI_BASE_URL after the docs are verified. Backend env only, never logged.
2. `backend/bulkapi.py`: launch client using the documented encryption, and a game catalogue sync.
3. Callback `POST /api/bulkapi/callback`: verify the signature, check source IPs, process idempotently using the existing `game_transactions` unique index, and debit or credit `promo_balance`.
4. GGR ledger: provider-wise GGR, plus tracking of the prepaid BULKAPI GGR wallet balance.
5. Tests: auth, launch, balance sync, bet/win/rollback, duplicate callbacks and each enabled provider. Run with real calls only.
