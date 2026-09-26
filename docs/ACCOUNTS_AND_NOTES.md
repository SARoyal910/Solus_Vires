# Accounts + Private Notes/Evidence Log — Implementation Notes

Documents what was built in the accounts and private-notes feature pass: why it exists, every tool/library added, every file touched, and how the pieces fit together. Companion to [ARCHITECTURE.md](ARCHITECTURE.md) (system-wide status) and the root [README.md](../README.md) (user-facing summary).

## Why this exists

The site was Phase 1 only: static pages plus a stateless, content-blind contact form. The goal is to grow Solus Vires into a real victim-advocacy platform with three eventual capabilities: private per-survivor abuser/case records, secret evidence logging, and a trusted-contact "I'm OK" check-in system.

Two scoping decisions shaped this build:

1. **No public abuser registry.** A crowdsourced/public database of named "abusers" was rejected — it is a defamation risk (naming someone without a conviction is legally exposed) and a retaliation-safety risk (an abuser could search it and identify who reported them). Instead, abuser/case info is a **private field set tied only to the survivor's own account**, never public, never cross-user visible, never queryable by anyone else.
2. **Build order:** accounts + secret evidence log first. The trusted-contact check-in system is explicitly deferred to a later phase — nothing for it exists yet.

This pass covers only decision #2's target.

## Key concepts used

A glossary of the security/architecture concepts this build leans on, for anyone reading the code without that background:

- **Zero-knowledge encryption** — the server stores only ciphertext and never holds a key capable of decrypting it. Not a marketing term here: it means a database breach, a subpoena, or a compromised operator all yield unreadable noise, not survivor content. Applied to `case_profiles` and `evidence_entries` only (see below) — not to the plain contact form, which is unencrypted-in-transit-only.
- **Client-side (in-browser) encryption** — the mechanism that makes zero-knowledge possible: encryption/decryption happens in the user's browser via the native WebCrypto API (`crypto.subtle`), before data is ever sent over the network.
- **PBKDF2 (Password-Based Key Derivation Function 2)** — turns a human-memorable PIN into a cryptographic key, deliberately slowed down (600,000 hash iterations) so that guessing PINs by brute force is computationally expensive even if an attacker gets the salt.
- **AES-256-GCM** — the actual encryption cipher used on the derived key. GCM is an *authenticated* mode: it appends a tamper-evident tag to the ciphertext, so decrypting with the wrong key doesn't produce garbled-but-plausible output, it fails cleanly and detectably ("Incorrect PIN" rather than corrupted text).
- **Salt** — a random per-user value mixed into the PBKDF2 derivation so two users with the same PIN don't produce the same key, and so precomputed ("rainbow table") attacks don't work. Not secret — safe to store server-side in the clear, unlike the PIN itself.
- **Argon2id password hashing** — the current OWASP-recommended algorithm for turning a login password into a stored hash that resists both GPU-cracking and side-channel attacks. Used for account passwords and recovery codes (never for the Notes PIN, which uses PBKDF2 for browser-native key derivation instead of hash comparison).
- **Opaque session tokens** — a random, meaningless-on-its-own token handed to the browser in a cookie; the server maps it (as a hash) to a session row that can be deleted at any time for instant, real logout. Contrasted with **JWT** (a self-contained, signed token that stays valid until it expires, harder to revoke early) — rejected here specifically because instant revocation is a safety feature for this app, not a nicety.
- **`HttpOnly` / `SameSite=Strict` cookies** — browser-enforced protections: `HttpOnly` keeps the session token invisible to page JavaScript (blocks a class of token-theft via XSS), `SameSite=Strict` stops the cookie from being sent on cross-site requests (blocks a class of CSRF).
- **Defense against DV-specific threats, not just generic ones** — several choices exist because the realistic attacker for this app is often someone with physical or account access to the survivor's own device, not an anonymous internet attacker: no email/SMS account recovery (a shared inbox/phone plan is a leak vector), a separate unrecoverable Notes PIN (so password reset can't double as an evidence-access bypass), generic page/nav labeling (so a shoulder-surf reveals nothing), and auto-lock on idle/tab-hide.
- **Structural privacy, not just access-control privacy** — there is no table anywhere that could hold cross-user or public data about a named "abuser." The one-per-user unique constraint on `case_profiles.user_id` makes the "never public" property true by schema design, not merely by a permission check that could have a bug.

## New tools and libraries

| Tool | Where | Why |
|---|---|---|
| **SQLAlchemy 2.0** (sync) | `backend/app/core/db.py`, `backend/app/models/` | ORM/engine. Sync (not `asyncio`+`asyncpg`) to keep the dependency footprint small — FastAPI runs sync route handlers in a worker thread pool automatically, so no async session complexity was needed for a feature this size. |
| **psycopg[binary]** | driver behind SQLAlchemy | Postgres driver; binary wheel avoids needing build tooling in the Docker image. |
| **argon2-cffi** | `backend/app/core/security.py` | Password/recovery-code hashing via `argon2.PasswordHasher` (Argon2id) — OWASP's current top recommendation. Used directly instead of `passlib`, which is unmaintained and has a known interaction with modern `bcrypt`. |
| **Alembic** | `backend/alembic.ini`, `backend/migrations/` | Schema migrations, adopted from day one rather than `Base.metadata.create_all()`. The project's own `docs/ARCHITECTURE.md` already called for migrations before this kind of irreplaceable-data feature, and retrofitting Alembic after real survivor data exists would be far riskier than adopting it now. |
| **WebCrypto (`crypto.subtle`)** | `html/evidence-crypto.js` | Native browser API — PBKDF2 key derivation + AES-256-GCM encryption. No external JS crypto library, no bundler. Available dependency-free in every evergreen browser. |

No new frontend build tooling was introduced — the site remains plain HTML/CSS/JS.

## Architecture decisions and why

**Login by username, not email/phone.** Avoids the classic DV-tech failure mode where a password-reset link or verification code passes through an inbox or phone plan the abusive person can also see.

**Sessions are opaque, DB-backed tokens, not JWT.** A random token (`secrets.token_urlsafe(32)`) is set in an `httponly`, `SameSite=Strict` cookie; only its SHA-256 hash is stored server-side in the `sessions` table. This buys instant, real revocation — `/api/auth/logout-all` deletes every session row for a user immediately, which matters if a survivor says "the person who hurts me has my phone." A JWT can't be un-issued without a blocklist; this design needed one fewer moving part and one fewer secret (no signing key to generate, store, or rotate).

**Recovery via one-time codes, not email/SMS.** Ten single-use recovery codes are generated at registration, hashed the same way as passwords, and shown to the user exactly once. If both password and all codes are lost, the account is unrecoverable by design — stated plainly in the UI, not hidden.

**Evidence encryption is zero-knowledge (client-side), not server-side-at-rest.** This extends an existing precedent already in the codebase: `backend/app/services/contact.py`'s `ContactService` deliberately never logs survivor-provided message content. Server-side-at-rest encryption still leaves the operator (or anyone who breaches, subpoenas, or compels them) able to produce plaintext. With zero-knowledge encryption, the database only ever holds ciphertext + IV; the operator can truthfully say they never had the ability to read it.

Concretely: a separate **Notes PIN**, distinct from the login password, derives an AES-256-GCM key in-browser via PBKDF2-SHA256 (≥600,000 iterations, a per-user random salt generated client-side and stored server-side since a salt isn't secret). The key is a non-extractable `CryptoKey` that lives only in memory — never in `localStorage`, never transmitted. It must be re-derived from the PIN on every page load.

The Notes PIN is deliberately **separate from the login password and has no recovery path.** Password recovery resets access to the account; it must not also grant access to encrypted evidence, or the "zero-knowledge" property would be fiction. The explicit tradeoff — forgetting the PIN means permanent, unrecoverable loss of that content — is surfaced in the `log.html` UI at setup time, not hidden.

**No global "abuser" table exists anywhere.** `case_profiles` is one encrypted row per user (enforced by a unique constraint on `user_id`), referencing nothing outside its owner. This makes "not a public database" structurally true, not just access-control-enforced.

**Generic labeling, not a full UI disguise.** The nav/page-title for the notes page reads "Notes," not "Evidence Log," so a shoulder-surf glance at a browser tab or history entry reveals nothing distinctive. A full disguised skin (e.g., mimicking a weather app) was considered out of scope for this pass.

## Data model

Five new tables, added via Alembic migration `backend/migrations/versions/0001_initial.py`:

```
users            id, username (unique), password_hash, evidence_salt,
                 failed_login_count, locked_until, created_at, last_login_at

recovery_codes   id, user_id (fk), code_hash, used_at, created_at

sessions         id (sha256 of the cookie token), user_id (fk),
                 created_at, expires_at, last_seen_at

case_profiles    id, user_id (fk, unique — one per account), ciphertext, iv,
                 created_at, updated_at

evidence_entries id, user_id (fk, indexed), ciphertext, iv,
                 created_at, updated_at
```

`case_profiles` and `evidence_entries` never store anything except opaque ciphertext + IV plus server-assigned timestamps and the owning `user_id` — no plaintext field of any kind, not even an entry "type," to avoid leaking structural metadata.

## API surface

New routers, following the existing `api/` → `schemas/` → `services/` layering already used by `contact.py`:

**`backend/app/api/auth.py`** (`AuthService` in `backend/app/services/auth.py`)
- `POST /api/auth/register` — `{username, password}` → creates the account + 10 recovery codes, returned once.
- `POST /api/auth/login` — sets the session cookie. Failed attempts slow down only the guessing (IP, username) pair, never the account as a whole (`core/login_throttle.py`, Phase 2 P2-A5; the old 8-strikes account lock let anyone who knew a username lock the survivor out).
- `POST /api/auth/logout` — deletes the current session.
- `POST /api/auth/logout-all` — deletes every session for the account.
- `POST /api/auth/recover` — `{username, recovery_code, new_password}`; single-use code check, invalidates all sessions, never touches evidence data.
- `GET /api/auth/me` — current username + whether a Notes PIN has been set up.

**`backend/app/api/evidence.py`** (`EvidenceService` in `backend/app/services/evidence.py`), all behind a `get_current_user` dependency, scoped strictly to the caller's `user_id`, returning 404 (not 403) on any cross-user access attempt:
- `GET/PUT /api/evidence/salt` — the PBKDF2 salt (set-once).
- `GET/PUT /api/evidence/case-profile` — the encrypted case-profile blob.
- `GET/POST /api/evidence/entries`, `PUT/DELETE /api/evidence/entries/{id}` — encrypted log entries.

`EvidenceService` never inspects, transforms, or logs ciphertext content — its log lines record only structural events like `evidence_entry_created`, mirroring `ContactService`'s pattern.

## Frontend

- **`html/account.html`** — register / log in / one-time recovery-code display / "log out everywhere" / password recovery.
- **`html/log.html`** (nav label: "Notes") — PIN setup, PIN unlock, private case-profile editor, add/view/delete encrypted entries. Auto-locks after ~4 minutes idle or when the tab is hidden (`visibilitychange`); manual "Lock now" button. The existing Quick Exit (`html/shared.js`) already wipes the in-memory key for free since it discards the JS heap.
- **`html/evidence-crypto.js`** — dependency-free helper module: `generateSaltBase64`, `deriveKey`, `encryptJSON`, `decryptJSON`. Loaded only by `log.html`, not by `shared.js` (which loads on every public page).
- **`html/shared.css`** — one addition, `.recovery-codes` (a monospace grid for displaying the one-time codes clearly). Everything else in `account.html`/`log.html` reuses the existing design system (`.card`, `.btn`, `.notice`, `.status`, standard form styling) — no new visual design was introduced.
- Every existing page's nav gained one `Account` link (`index.html`, `resources.html`, `safety.html`, `legal.html`, `partners.html`, `emergency.html`, `contact.html`), placed the same way the existing `Contact` link already was.

## Backend wiring

- `backend/app/main.py` — registers the new `auth` and `evidence` routers.
- `backend/app/core/config.py` — added `database_url`, `session_cookie_secure`, `session_ttl_days` settings (env-driven, same `Settings` dataclass pattern as before).
- `backend/app/core/middleware.py` — extended the existing no-store `Cache-Control` rule (previously just `/contact`) to also cover `/api/auth`, `/api/evidence`, `/account.html`, `/log.html`.
- `backend/requirements.txt` — added `sqlalchemy`, `psycopg[binary]`, `argon2-cffi`, `alembic`.
- `backend/Dockerfile` — now copies `alembic.ini`/`migrations/` and runs `alembic upgrade head` before `uvicorn` starts.
- `docker-compose.yml` — `api` service now depends on `db`, gets `DATABASE_URL` built from `POSTGRES_PASSWORD`, and `SESSION_COOKIE_SECURE=true` in the Docker/production path.
- `.env.example` — added `DATABASE_URL` (placeholder), `SESSION_COOKIE_SECURE`, `SESSION_TTL_DAYS` for local non-Docker development. No JWT signing key needed, per the opaque-session design above.
- `README.md` / `docs/ARCHITECTURE.md` — updated to describe the new feature and its real limitations (see below), and to mark each item in the "Production Requirements Before Sensitive Features" checklist as done / partially done / not done against this build.

## What was verified statically (before Docker was running)

- Backend imports cleanly and all new routes register (`python -c "from backend.app.main import create_app; create_app()"`).
- `backend/requirements.txt` installs cleanly into the project venv.
- The Alembic migration produces correct SQL in offline dry-run mode (`alembic upgrade head --sql`) — table/column/constraint definitions match the SQLAlchemy models.
- Inline JS in `account.html`, `log.html`, and `evidence-crypto.js` passes `node --check`.

## What was verified live, against a running Docker stack

Docker Desktop was started and `docker compose up --build` run against this repo. One pre-existing environment issue surfaced and was fixed along the way (not caused by this feature's code, just local-environment state): **nginx had cached a stale IP for the `api` container** after `api` was restarted (nginx resolves `proxy_pass http://api:8000` once, not per-request). Fixed with `docker compose restart web`.

With those cleared, the following was exercised with `curl` through nginx at `https://localhost` (self-signed cert, `-k`), i.e. the real network path a browser would take, not a direct backend call:

- `POST /api/auth/register` → `200`, 10 recovery codes returned.
- `POST /api/auth/login` → `200`, session cookie set with the expected `HttpOnly` attribute.
- `GET /api/auth/me` → `200` with the cookie (correct username), `401` without it.
- `PUT /api/evidence/salt`, `POST /api/evidence/entries`, `GET /api/evidence/entries` → all `200`, correctly scoped to the logged-in user.
- **Zero-knowledge property, checked directly in the database and logs, not just asserted**: pushed a distinctive marker string as a stand-in ciphertext value, then confirmed via `docker exec ... psql -c "select ciphertext, iv from evidence_entries;"` that the DB holds only that opaque value, and `docker logs solusvires_api | grep` for both the marker and the plaintext password came back empty.
- `POST /api/auth/logout` → cookie cleared; `GET /api/evidence/entries` afterward correctly returned `401`.

One caveat on the zero-knowledge check above: the "ciphertext" pushed via `curl` was a hand-crafted base64 stand-in, not real AES-GCM output — it proves the *API and database layer* correctly treat the field as opaque (never inspected, never logged), but on its own it doesn't exercise the actual in-browser crypto code.

The dev stack (`db`, `api`, `web`) was left running after this test. One test account (`testsurvivor`) and one test entry exist in the dev database. `docker compose ps` to check status, `docker compose down` to stop it.

## What was verified: the real crypto module itself (no browser available)

The Chrome extension needed for a live browser session wasn't connected, so instead of stopping at the caveat above, `html/evidence-crypto.js` was run unmodified under Node's WebCrypto implementation (`crypto.subtle` is standardized, not browser-specific) to prove the actual PBKDF2/AES-GCM code — not a stand-in — behaves correctly:

- `generateSaltBase64` → produces a random per-user salt.
- `deriveKey(pin, salt)` → derives an AES-256-GCM key via PBKDF2-SHA256.
- `encryptJSON(key, entry)` → encrypting `{entry_date, text: "UNIQUE_REAL_CRYPTO_MARKER_ABC"}` produced ciphertext/IV with **no trace of the plaintext marker string** in either output field.
- `decryptJSON(correctKey, ...)` → round-tripped back to the exact original object.
- `decryptJSON(wrongKey, ...)` → threw a clean `OperationError` (AES-GCM's authentication tag rejecting the wrong key) rather than returning corrupted-but-plausible plaintext — confirms `log.html`'s "Incorrect PIN" handling has a real, cryptographically sound signal to key off, not just a hope.

This validates the cryptographic core end-to-end. What's still unverified is purely the DOM/UI layer wired around it:

## Verified live in a real browser — and a real bug found and fixed

Once the Chrome extension connected, `account.html` and `log.html` were driven directly (via `http://127.0.0.1:8000`, a local `uvicorn` run against the same dockerized Postgres over a temporarily-published port, to sidestep the dev stack's self-signed HTTPS cert rather than fight Chrome's interstitial):

- Registered a fresh account through the real UI — recovery codes displayed, "Continue to log in" correctly stayed disabled until the "I have saved these codes" checkbox was checked.
- Logged in through the real UI — landed on the "You are logged in as ..." view.
- Set a Notes PIN through the real UI, added an entry with a distinctive marker through the real UI — it rendered decrypted correctly, and the database row for it held only real AES-GCM ciphertext (no trace of the marker).
- Reloaded — correctly re-prompted for the PIN (in-memory key not persisted).

**Bug found: a wrong PIN did not fail.** Typing an incorrect PIN silently proceeded into the unlocked view instead of showing an error and staying locked — the profile fields came back blank and existing entries showed "Unable to decrypt," but the page still presented itself as unlocked. This was worse than cosmetic: if a survivor mistyped their PIN and then added a *new* entry while in this state, that entry would be encrypted under the wrong (mistyped) key permanently, with no error at write time — silent, unrecoverable data loss disguised as a normal save.

Root cause: `log.html`'s unlock handler derived a key from whatever was typed and unconditionally entered the unlocked view — it never attempted to decrypt anything to confirm the PIN was actually correct before declaring success.

**Fix applied** (`html/log.html`): added a `verifyKey(key)` check that runs before treating an unlock as successful. It tries to decrypt the existing case profile (or, if none exists yet, the first existing entry) with the freshly derived key; only on a successful decrypt does the page unlock. If decryption fails, the key is discarded, the page stays on the locked screen, and "Incorrect PIN." is shown. Re-verified after the fix, both via direct DOM/event testing and through the real UI: wrong PIN → stays locked, shows "Incorrect PIN.", `cryptoKey` cleared; correct PIN → unlocks normally, existing entry still decrypts correctly (no regression).

One inherent limitation this fix cannot close, already true of zero-knowledge designs generally: on the very first-ever unlock attempt, before anything has ever been saved, there is nothing to test-decrypt against, so an incorrect PIN at that exact moment cannot be distinguished from a correct one. This only matters in the narrow window between PIN setup and the first saved item, and is disclosed as a residual edge case rather than something to silently paper over.

**Closed in Phase 2 (P2-A3):** PIN setup now also stores a key-check (a constant encrypted under the PIN), and unlock decides by decrypting it, so a wrong PIN is rejected even on an empty vault. Accounts from before the change are verified against saved data once and get a key-check written; if nothing was ever saved, the PIN must be entered twice. See `docs/PHASE2_PLAN.md`.

- The "Lock now" button was also exercised directly (same code path as the idle-timeout auto-lock) and correctly returns to the PIN-locked screen.

## Not yet re-verified after the fix

- The idle-timeout auto-lock specifically (as opposed to the manual "Lock now" button, which uses the same underlying function and was tested) — the timer is 4 minutes, which wasn't waited out live.
- Login lockout/backoff after repeated failed attempts, and the recovery-code reset flow, end-to-end through the `account.html` UI (as opposed to the raw API, which was tested).
- Cross-user isolation (a second account correctly getting `404`, not data, for the first account's records) — verified structurally in the query logic, not re-exercised live in this session.

## Explicitly deferred — not built in this pass

- Trusted-contact check-in/alerts (the next planned phase).
- File/photo evidence upload — text-only for now; photo EXIF metadata can itself leak GPS location, which is a safety reason to defer, not just a scope cut.
- A full disguised/skinned UI beyond generic page/nav labeling.
- MFA, OAuth, passkeys.
- Admin or partner-facing tooling; there is a single user role, no RBAC.
- Structured audit logging — deferred pending an actual design for who such logs would be for and how they'd be protected, since with zero-knowledge content there's little upside and some risk (e.g., login IPs) to logging by default.
- A public abuser registry — deliberately rejected, not deferred (see "Why this exists" above).
- Rate limiting/abuse detection beyond the basic login lockout; no CAPTCHA or WAF-level protection.
- Backup/restore testing; a defined data retention/deletion policy beyond user-initiated delete.
- A Notes PIN change/rotation flow — the data model supports it (the salt lives on `users`, not per-entry), but the re-encrypt-all-entries UI is a fast-follow, not MVP-blocking.
- **Legal review.** Per the project's own architecture doc and README, this remains a hard prerequisite before any real-world use with actual survivors. This build is a technical milestone, not a launch-ready product.
