# Phase 2 Development Plan

**As of:** 2026-09-26, branch `dev` at `e175ccf`
**Status (2026-10-02):** Sprints 0–1 and the Sprint 4 content are live (deployed 2026-09-26). Sprint 2, the code side of Sprint 3, Sprint 5, and Sprint 6's features (E7, E8, E9) were merged on `phase2`, tested, and **deployed 2026-10-04** (`main` at `2b81477` on the droplet, smoke green): merges `48da5dc` (lane/a: backend, check-ins, contact form), `b45c8bb` (lane/c: ops, docs, content, offline copy), `972ac3a` (lane/b: CSP, vault, Quick Exit, plain view). A ✅ in the tables below is Done in this plan's sense: merged, tested in CI, deployed. Still open: everything waiting on the owner or on outside reviewers, listed in `docs/TODO.md`. What's live: `docs/PROGRESS.md`.
**Inputs:** `REVIEW_ENGINEERING.md`, `REVIEW_USER.md`, `DESIGN2.md`, `TODO.md`
**Relationship to `DESIGN2.md`:** `DESIGN2.md` says *what* Phase 2 is and *why*. This file says *how and in what order*: tickets, files, migrations, tests, and the gate for each sprint. If the two disagree on scope, `DESIGN2.md` wins; if they disagree on sequencing, this file wins.
**Audience:** This site is for survivors of every gender, men included. The user review's four personas happen to all be women, so Sprint 4 adds a male survivor's path explicitly (P2-D9) and every content ticket is written and reviewed with men in mind. See guardrail in §6.
**Coverage:** Appendix A maps every finding in both reviews, every `DESIGN2.md` deliverable, and every open `TODO.md` item to a ticket here, or to an explicit deferral. Nothing from those four sources is dropped silently.

---

## 0. How to read this plan

- **Ticket IDs** are `P2-<workstream><n>` (e.g. `P2-A3`). Workstream letters match `DESIGN2.md` section 3.
- **Closes** names the review finding(s) a ticket resolves (`H1`, `M4`, `L2` from the engineering review; `U-<n>` for row *n* of the "fix this month" table in the user review).
- **Size:** S = a day or less, M = 2-4 days, L = a week+. One part-time developer is assumed, so sprints are defined by *exit gates*, not calendar dates.
- **Every code ticket ships with a test** unless it says otherwise. A ticket without its test is not done.
- A ticket is **Done** when: merged to `dev`, test green in CI, deployed, and (if it touches the live site) confirmed by the smoke probe.

---

## 1. Open decisions

Each blocks the tickets listed; D1 must be settled before Sprint 1 ends, the rest before the sprint that contains their tickets. Recommendations are from `DESIGN2.md` section 6; record the final choice here.

| # | Decision | Recommendation | Blocks | Decided |
|---|---|---|---|---|
| D1 | Sign-ups: invite-gate or prototype banner | **Invite-gate** (`BETA_SIGNUPS_ENABLED=false` + invite codes) | P2-A7 | ✅ Invite-gate (2026-09-26) |
| D2 | Name on the About page | Real individual name + stated intent to seek a nonprofit sponsor | P2-C1 | ✅ Real name (2026-09-26); exact wording confirmed when writing P2-C1 |
| D3 | Contact form: wire to monitored inbox, or remove | Remove until someone can commit to a response window | P2-C5 | ✅ **Monitored inbox** (2026-09-26): wire to the owner's email via Brevo with a stated response window and a 'not for emergencies' line. P2-C5 changes accordingly |
| D4 | Alert email: always-send or fallback-only | Always-send; fix the docs | P2-A12 | Default: recommendation, open to change |
| D5 | Notes PIN minimum | 12 characters, passphrase encouraged | P2-A10 | ✅ 12 characters (2026-09-26) |
| D6 | Who is the advocacy reviewer / legal counsel | Identify and contact people during Sprint 1; send review packets in Sprint 3 (P2-C3/C4). External lead time is the long pole | P2-C3, P2-C4 | ☐ |
| D7 | CAPTCHA on public endpoints (`TODO.md`) | **Defer.** Hosted CAPTCHAs (Turnstile, hCaptcha) are third-party scripts, which breaks the "no third parties on a monitored device" principle. The invite gate (P2-A7) plus real per-IP limits (P2-A1) cover registration for now. Revisit a self-hosted proof-of-work only if abuse alerting (P2-F3) shows a need. | — | Default: recommendation, open to change |
| D8 | Audit logging (`TODO.md`) | Make the decision inside the threat model (P2-C6): the default is to keep no login-IP history, and to write down why. | P2-C6 | Default: recommendation, open to change |
| D9 | How visibly to name men | **Say it plainly once, then write neutrally everywhere.** A single line on the homepage and About ("For anyone being hurt by a partner or family member, whatever your gender") plus a dedicated page. Gendered imagery or a separate "men's site" would split the resource. | P2-D1, P2-D9 | Default: recommendation, open to change |

---

## 2. Sprint map

```
Sprint 0  Harness            ──►  Sprint 1  Stop the bleeding  ──►  Sprint 2  Hardening tail
(tests + CI skeleton)             (H1–H6, backups)                   (M1–M10, L-items, CSP)
                                                                           │
                                   Sprint 3  Trust gate  ◄─────────────────┘
                                   (About, privacy, threat model; start external reviews)
                                           │
                     ┌─────────────────────┴───────────────────┐
             Sprint 4  Content                         Sprint 5  Survivor features + ops
             (homepage, abuse, safety plan,            (export, Quick Exit v2, theme,
              help-someone, Spanish, local)             check-in reliability, monitoring)
                     └─────────────────────┬───────────────────┘
                                   Sprint 6  Close-out
                                   (external review feedback, photo evidence, PWA, freeze)
```

**Mapping to `DESIGN2.md` milestones:** M0 = Sprints 0–1 (+ Sprint 2's Medium fixes, which `DESIGN2.md` puts in Workstream A) · M1 = Sprint 3 (+ the rest of Workstream B in Sprint 2) · M2 = Sprint 4 · M3 = Sprints 5–6. Sprint 2 is split out of M0 only so the six Highs can ship on their own without waiting on the Medium fixes.

Sprints 4 and 5 can interleave; content and features touch different files. External legal/advocacy review (P2-C3/C4) runs in the background from Sprint 3 onward and its feedback lands in Sprint 6.

---

## Sprint 0 — Harness (do this first, it makes everything else cheaper)

**Goal:** every later fix lands with a test that runs on every push.

| ID | Ticket | Files | Size | Closes |
|---|---|---|---|---|
| ✅ P2-B1 | Pinned `requirements.txt` + `requirements-dev.txt` (pytest, ruff); `pyproject.toml` holds tool config only, so the Dockerfile is unchanged. Pin Python 3.12 in `.python-version`, recreate the venv on 3.12. | `backend/pyproject.toml`, `backend/Dockerfile`, `.python-version` | S | M10 |
| ✅ P2-B2 | Test scaffolding (`scripts/test.sh` + `docker-compose.test.yml`: Python 3.12, tmpfs Postgres, separate compose project so it can't touch live containers; conftest refuses any DB not named `*_test`): `pytest`, `httpx`, a `conftest.py` that spins a throwaway Postgres (Docker service in CI, `DATABASE_URL` override locally), runs `alembic upgrade head`, and yields a `TestClient` + a `register_and_login()` helper. | `backend/tests/conftest.py` | S | M10 |
| ✅ P2-B3 | First tests (27) against *current* behaviour (they document the baseline; some will be rewritten by Sprint 1 fixes): HMAC token sign/verify and tamper rejection; register → login → logout; evidence CRUD ownership (user B cannot read user A); `is_overdue()` edge cases; account deletion cascade. | `backend/tests/test_*.py` | M | M10 |
| ▶ P2-B4 | GitHub Actions (`.github/workflows/ci.yml` written; runs once pushed; making it a required check on `main` is a GitHub setting): ruff + pytest with a Postgres service; required status check on `main`. | `.github/workflows/ci.yml` | S | M10 |
| ✅ P2-B5 | Header probe script (baseline against live 2026-09-26: HSTS missing everywhere; all four headers missing on account/log/checkin/checkin-invite, confirming H2): curls a list of paths, asserts `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `X-Robots-Tag` (and later HSTS/CSP). Takes a base URL so it runs against CI nginx *and* live. Add it to CI against a built nginx container. **It will fail on `/log.html` today — that's the point; mark it expected-fail until P2-A2.** | `scripts/probe_headers.sh`, CI job | S | H2 (detection) |

**Exit gate:** CI green on `dev` with ~10 tests; probe runs in CI and against `https://solusvires.com`.

---

## Sprint 1 — Stop the bleeding (all six Highs)

**Goal:** every High finding fixed, tested, deployed, and probed live. Order within the sprint is by blast radius on the live site.

### ✅ P2-A2 · Security headers on every location — S — closes H2, L7
*Done: `nginx/snippets/security-headers.conf` included at server level and in the private-pages location; `/api/*` hides the app's duplicate copies. Per-page robots `<meta>` tags kept as a second layer rather than removed. Probe green against a local nginx; goes live on deploy.*
- Move the four `add_header ... always` lines into `nginx/snippets/security-headers.conf`; `include` it at server level **and** inside the `account|log|checkin|checkin-invite` location (and any future location with its own `add_header`).
- Add `Strict-Transport-Security "max-age=31536000" always` in the same snippet (short `max-age` first if nervous; no `preload` yet). Partially closes L2.
- Remove the per-page `<meta name="robots">` inconsistency: rely on the header everywhere.
- **Test:** P2-B5 probe flips from expected-fail to pass. Run it against live after deploy.

### ✅ P2-A1 · Real client IP through Cloudflare — S — closes H1 (and unblocks M6)
*Done: nginx restores the visitor IP from `CF-Connecting-IP`, trusted only from Cloudflare's published ranges (`scripts/update_cf_ranges.sh`); the app trusts `X-Real-IP` only with `TRUST_PROXY_HEADERS=true`. (An earlier note here claimed the origin was Docker Desktop on the owner's Mac; that was wrong. Production is the DigitalOcean droplet; the Mac runs a local copy.)*

### ✅ P2-A1b · Only Cloudflare may reach the origin — S — defense in depth, optional
*Done 2026-09-26: Global AOP on in Cloudflare; nginx now requires the client certificate. Confirm on the droplet after deploy (test below).*
- Rate-limit spoofing is already closed by P2-A1 (only Cloudflare ranges may set the visitor IP). This hides the droplet from direct connections entirely, so nobody can bypass Cloudflare's own protections.
- Turn on **Authenticated Origin Pulls → Global** (Cloudflare's shared client cert; "Zone-level" means uploading your own) in the Cloudflare dashboard first, then include `nginx/snippets/authenticated-origin-pulls.conf` (staged, with Cloudflare's CA). Wrong order takes the site down. Alternatively, a DigitalOcean firewall allowing 443 only from Cloudflare's ranges does the same at the network level.
- **Test:** a direct `curl --resolve solusvires.com:443:<droplet-ip>` is refused; the site still loads through Cloudflare.

### ✅ P2-A3 · Wrong PIN can never fork the vault — S — closes H3
*Done (migration 0003, `PUT /api/evidence/key-check` write-once backfill, `log.html` checkPin; P2-B6 crypto tests pulled forward to `tests/web/`). Also fixed a second silent-loss bug found on the way: PIN setup ignored a failed or 409 salt save and kept encrypting under a salt the server never stored. PIN minimum raised to 12 (D5) in the same form. Browser-checked 2026-09-26 in headless Chrome against the preview: 16/16 (`tests/browser/notes_pin.mjs`), covering new accounts, legacy accounts with and without saved notes, and the 12-character minimum.*
- Migration `0003_evidence_key_check`: add `users.evidence_key_check_ciphertext` and `users.evidence_key_check_iv` (nullable `Text`).
- API: extend `GET/PUT /api/evidence/salt` (`backend/app/api/evidence.py`, `schemas/evidence.py`) to carry the key-check blob alongside the salt. The server stores it opaquely; it's ciphertext of a constant.
- Client (`html/evidence-crypto.js`, `html/log.html`):
  - At PIN setup: derive key, encrypt a fixed constant (e.g. `"solusvires-key-check-v1"`), PUT salt + key-check together.
  - `verifyKey()`: if a key-check exists, decrypt it — that is the only test. Delete the "first-ever unlock is allowed through unverified" path.
  - **Backfill for existing users:** if no key-check exists but entries/profile do, verify against them as today, and on success write the key-check. If no key-check *and* no data exists, treat it as setup: ask for the PIN twice, then write the key-check.
- **Tests:** API round-trips the blob; ownership. Client logic covered by P2-B6 (Sprint 2) — until then, a manual test script in the PR description: set PIN → reload → wrong PIN on empty vault is rejected.

### ✅ P2-A5 · Lockout can't be weaponised against the survivor — M — closes H5
*Done: `core/login_throttle.py` (free attempts 3, then 1-2-4-8-16-30 s per (IP, username), `Retry-After`); account counter is a signal only; recovery clears every pending wait for that username. Unknown usernames are throttled the same way so the throttle can't reveal which names exist.*
- Replace the account-only hard lock in `backend/app/core/security.py`:
  - Track failures per `(client_ip, username_lower)` in the in-process limiter (same single-process caveat as today's limiter; documented).
  - Progressive delay per pair (e.g. 0, 0, 1s, 2s, 4s … capped at 30s) instead of a hard lock.
  - Keep a per-username counter only as a *soft* signal (log / future alert), never a lock.
  - A successful recovery-code login (`/api/auth/recover`) always succeeds regardless of failure counters.
- Leave `users.failed_login_count` / `locked_until` columns in place for one release, unused; drop them in a later migration.
- **Tests:** 8 failures from IP A do not block a correct login from IP B; delay grows for the attacking pair; recovery bypasses.

### ✅ P2-A6 · Push device can't be silently stolen by another invite — M — closes H4
*Done (migration 0004). Also: re-subscribing refreshes the device's keys under every contact it serves, and an expired device is removed for all of them. The survivor-visible "a contact's push died" flag moves to P2-E5, which owns that UI.*
- Minimal fix now (keeps the schema small): migration `0004_push_subscription_scope` drops the global unique on `push_subscriptions.endpoint` and adds `UNIQUE(trusted_contact_id, endpoint)`.
- `services/checkin.py` `add_subscription()`: upsert on `(trusted_contact_id, endpoint)` instead of re-pointing an existing row.
- Dead-endpoint pruning (410/404 from the push service): delete **every** row with that endpoint, and set a flag the survivor can see (feeds P2-E5).
- **Tests:** one endpoint subscribed under two invite tokens → both contacts report 1 device → an alert for either survivor sends to it.

### ✅ P2-A7 · Registration gate — S — closes H6 (needs D1)
*Done: invite-only by default (`BETA_SIGNUPS_ENABLED=false`); codes in `BETA_INVITE_CODES`, compared in constant time; no codes configured = sign-ups paused with a plain message. The gate runs before the username check, so it can't be used to probe usernames. Existing accounts, login, and every resource page are unaffected.*
- If invite-gate: setting `BETA_SIGNUPS_ENABLED` (default `false`) + `BETA_INVITE_CODES` (comma-separated, hashed compare) checked in `services/auth.py` `register()`. `account.html` shows an "Invite code" field and a plain explanation when signups are closed. Existing accounts unaffected.
- If banner: a non-dismissible notice on `account.html`, `log.html`, `checkin.html`.
- Either way, record the decision in section 1 of this file.
- **Tests:** register without code → 403 with a clear message; with code → 201.

### ✅ P2-F1 · First backup and restore — S — closes engineering "before next sprint" #4
*Done 2026-09-26: `age` on the droplet, backup taken before the Sprint 1 deploy, nightly cron installed, and that droplet backup decrypted and restored cleanly on the Mac (logged in `docs/RUNBOOK.md`). Owner to-do: move `~/solusvires-backup-key.txt` off the Mac; copy backups off the droplet periodically or enable DigitalOcean backups.*

### ✅ One-liner copy fixes that ride along — S — closes U-9 (partial)
*Done on every page's nav; Partners stays reachable from Resources.*
- `checkin.html`: "You're being tracked for check-ins" → "Your check-in schedule is on".
- Nav: "Account" → "Notes & Check-ins"; move Partners from primary nav to footer (`html/shared.js` or wherever the nav is rendered, plus each page if it's static).

**Exit gate:** H1–H6 closed; probe green against live; CI green; one backup restored and documented; D1 recorded.

**Deployed 2026-09-26** (`main` at `e36b0ab` on the droplet): live probe green on all 13 paths, sign-up gate answering, direct-to-droplet connections refused, migrations 0003/0004 applied, CI green. Droplet backup restored the same day. **Sprint 1 exit gate met.**

---

## Sprint 2 — Hardening tail

**Goal:** close the Medium findings and the cheap Lows, get a real CSP.

| ID | Ticket | Files | Size | Closes |
|---|---|---|---|---|
| ✅ P2-A8 | Alert pass guarded by `pg_try_advisory_lock(<constant>)`; skip the pass if not acquired. Default `CHECKIN_ALERT_LOOP_ENABLED=false` in `.env.example` (on in compose). Test: two concurrent `run_due_alerts_once()` → one alert. | `services/checkin.py`, `core/config.py` | S | M1 |
| ✅ P2-A9 | Unknown-username login verifies against a module-level dummy Argon2 hash. Test asserts the dummy verify is called, plus a coarse timing check (median of 20 unknown vs. 20 wrong-password logins within 2x), which is the `DESIGN2.md` "within noise" acceptance without being flaky. | `services/auth.py` | S | M2 |
| ✅ P2-A10 | PIN minimum 12 chars, simple strength hint, and copy: "This PIN is the only thing protecting your notes if our database is ever stolen." Show the no-recovery warning again before the first save (U review, Marisol #5). Existing shorter PINs keep working; prompt to change on next unlock. | `html/log.html` | S | M3 |
| ✅ P2-A11 | `update_schedule()` recomputes `next_deadline_at = (last_checkin_at or now) + interval` on every save while active. Test: shorten 168h → 12h moves the deadline. | `services/checkin.py` | S | M4 |
| ✅ P2-A12 | Alert email behaviour per D4; alert copy states the repeat cadence ("You'll get this again every 6 hours until they check in"). Fix `CHECKIN.md` and README to match. | `services/checkin.py`, docs | S | M5 |
| ✅ P2-A13 | Recovery codes: migration `0005_recovery_code_hash` adds a `code_sha256` column (HMAC-SHA256 with a server pepper setting); new codes stored that way and looked up by hash; old Argon2 rows still verified until used or regenerated. | `models/auth.py`, `services/auth.py`, `core/security.py` | S | M6 |
| ✅ P2-A14 | Throttle `last_seen_at` writes (only if older than 5 min); sweep expired sessions in the background loop. | `core/security.py`, `services/checkin.py` loop or new `core/maintenance.py` | S | M7 |
| ✅ P2-A15 | Move the source bind mount into `docker-compose.override.yml`; Dockerfile `CMD` runs only uvicorn; add `scripts/migrate.sh` (`docker compose run --rm api alembic upgrade head`) and put it in the deploy steps in `RUNBOOK.md`. | `docker-compose.yml`, `backend/Dockerfile` | S | M8 |
| ✅ P2-A16 | `main.py` refuses to start when `APP_ENV=production` and `CHECKIN_TOKEN_SECRET` is empty or `POSTGRES_PASSWORD` is a default. Test the startup check. | `main.py`, `core/config.py` | S | M9 |
| ✅ P2-A17 | `SameSite=Lax` on the session cookie. Test: cookie attribute. | `core/security.py` | S | L1 |
| ✅ P2-A4 | CSP: move the inline scripts in `account.html`, `log.html`, `contact.html` to `.js` files; add `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'` to the nginx snippet (check for inline `style=` attributes first). Probe asserts it. Click through every page. | `html/*`, `nginx/snippets/` | M | L2 |
| ✅ P2-B6 | Crypto round-trip test: run `evidence-crypto.js` under Node's WebCrypto (`node --test`) — derive, encrypt, decrypt, wrong-key rejection, key-check behaviour from P2-A3. Add to CI. | `html/tests/crypto.test.mjs` | M | M10, H3 |
| ✅ P2-B7 | Post-deploy smoke: `scripts/smoke.sh <base-url>` = header probe + `/api/health` + each page 200. Documented as the last deploy step. | `scripts/` | S | process |
| ✅ P2-B8 | (`wrangler.jsonc` and `html/_redirects` deleted 2026-10-02.) Delete `wrangler.jsonc` and `html/_redirects` (or document them as dead in `ARCHITECTURE.md` — recommend delete). Add `.dockerignore` entries for `.DS_Store`, `__pycache__`, and the venv, and delete the stray `.DS_Store` files. Write the deployment story into `ARCHITECTURE.md`: Cloudflare proxy → single Docker host, origin cert (Cloudflare Origin CA, valid to 2040), where backups go, and who gets paged. | root, `html/`, `backend/.dockerignore` | S | L3, L4, eng. process |
| ✅ P2-B9 | (Done 2026-09-26: PROGRESS is the status page with a "last verified" line; TODO is now owner-only; ARCHITECTURE/README/CHECKIN updated; PROJECT_REPORT marked historical.) Docs consolidation: `PROGRESS.md` is the one status page; relabel "Phase 2" there to "Phase 1 (prototype)" per `DESIGN2.md`; fix `ARCHITECTURE.md` "no rate limiting"; add "last verified against commit" lines. Move actionable `TODO.md` items that this plan now owns into a pointer to this file. | `docs/` | S | L5 |

**Exit gate:** all Medium findings closed; CSP live with no console violations; test count ≥ 25; probe asserts HSTS + CSP.

---

## Sprint 3 — Trust gate

**Goal:** a stranger can find out who runs the site and what it does with their data. External reviews requested.

| ID | Ticket | Size | Closes |
|---|---|---|---|
| ✅ P2-C1 | (Steven Royal, through Omnia Royal LLC; contact address still to come.) `/about.html`: who runs it (per D2), why, what it is and is not, how to reach a human. Linked from footer on every page and from the invite + alert emails. | S | U-1 |
| ◐ P2-C2 | (Terms section added and the statement updated for contact form, alert history, photos, export, plain view, 2026-10-02. Written from a code audit; awaiting counsel review. The audit led to turning off nginx/uvicorn access logs and capping Docker logs.) `/privacy.html` plus a short plain-language terms/disclaimer section: "not an emergency service, not legal advice, prototype status" (Priya's "no terms" finding; counsel reviews both). Privacy covers, exactly what is stored (username, password hash, recovery-code hashes, notes ciphertext, salt + key-check, contact emails and nicknames, push endpoints, schedule timestamps), what is not (IPs are held in memory only for rate limiting — verify this is true before writing it), retention, how to delete, what a subpoena could and could not obtain. | M | U-1 |
| ◐ P2-C3 | (Request packet drafted in `docs/legal/REVIEW_REQUEST.md`, **not sent**; owner picks counsel and sends.) Legal review request: package privacy statement, emergency-language claims, mandatory-reporting question, contact-email handling. Output lands in `docs/legal/`. | External | DESIGN2 §1.4 |
| ◐ P2-C4 | (Request packet drafted in `docs/advocacy/REVIEW_REQUEST.md`, **not sent**; owner picks the organization and sends.) Advocacy review request: one DV organization walks the site, notes flow, check-in flow. Ask for (or add a second reviewer with) experience serving male survivors, and ask them to read `/for-men.html` specifically. Output lands in `docs/advocacy/`. | External | DESIGN2 §1.5 |
| ✅ P2-C5 | (Built 2026-10-02. The form stays off, and the page says so, until the owner sets `CONTACT_INBOX_EMAIL`; reply window defaults to 7 days via `CONTACT_RESPONSE_DAYS`.) Contact form per D3 (monitored inbox): `services/contact.py` sends each message to `CONTACT_INBOX_EMAIL` via the existing Brevo client (fail-soft, like alerts); the form states the response window and "not for emergencies — call or text the Hotline" above the Send button; the confirmation says the same. Nothing is stored in the database. Test: message triggers one send; empty inbox setting refuses the form with a clear message rather than pretending. | S | U-10 |
| ✅ P2-C6 | `docs/THREAT_MODEL.md`: actors (abuser with device access, abuser who knows the username, DB compromise, hostile trusted contact, subpoena, Cloudflare/host), each with mitigations mapped to files and the tests that prove them. Fold in H1–H6 as worked examples. Record decisions D7 (CAPTCHA) and D8 (audit logging) and the MFA deferral here, with the reasoning. | M | TODO "threat model", "audit logging", "MFA" |

**Exit gate:** About + Privacy live and linked everywhere; C3 and C4 requests sent (dates recorded here); threat model merged.

---

## Sprint 4 — Content that helps someone who doesn't know what they need

All content tickets: every organization, number, and claim verified against its official source before merge (existing project standard). Cite sources in an HTML comment at the bottom of each page.

| ID | Ticket | Size | Closes |
|---|---|---|---|
| ✅ P2-D1 | Homepage hero rewrite: a one-line "whatever your gender" statement (D9), then three first actions — *In danger now?* (911 / text START to 88788) · *Not sure what this is?* (→ Is this abuse?) · *Want to think and plan?* (→ Safety planning). Funder-voice taglines move below the fold. | S | U-3 |
| ✅ P2-D2 | `/is-this-abuse.html`: patterns of coercive control, non-physical examples (financial, digital, isolation, threats about kids/pets/immigration), a short client-side self-reflection (nothing stored, nothing sent), next steps. Examples use neutral pronouns and include abuse by a female partner and in same-sex relationships, plus the tactics men describe most: being belittled for "letting" it happen, threats to make false accusations, and threats about access to the kids. | M | U-4 |
| ✅ P2-D3 | Safety Planning rewrite (`safety.html`): documents to gather (ID, birth certs, immigration papers, lease, bank cards, meds, school records), leaving checklist, shared phone plan / accounts / location sharing, pets, children, work, after leaving. Make it the deepest page on the site. | M | U-5 |
| ✅ P2-D3b | (Older adults section added to Safety and an Adult Protective Services card to Resources, 2026-10-02.) Populations the advocate serves every week (Priya #6): add sections (on Safety and Resources, or a short page each) for immigration status (survivor-facing, not just the attorney library), disability (including caregiver-as-abuser), teens and dating abuse, and children in the home. Each links at least one verified specialist organization. | M | U review (Priya #6) |
| ✅ P2-D4 | `/help-someone.html`: for friends, family, coworkers. Include "if the person is a man": don't joke or minimise, don't ask why he didn't just leave or fight back. Linked from the invite email and invite page. | S | U review (Priya #5) |
| ✅ P2-D5 | Invite email and invite page gain a "How to check this is real" line that links to `/about.html` (Jo #1: phishing worry). `/if-you-get-an-alert.html` for trusted contacts: call them, don't confront the partner, when to call police, what to say, what not to post. Linked from every alert email and push payload. | S | U-8 (part) |
| ✅ P2-D6 | Legal page depth: two plain paragraphs each on protective orders, what to bring, lease breaks, custody safety, immigration remedies (VAWA, U-visa) — information, not advice. State plainly that protective orders are available regardless of gender. Link WomensLaw *state* pages, not the homepage, with a note that despite the name it serves people of every gender. | M | U review (Marisol #6) |
| ✅ P2-D7 | Local finder (state → WomensLaw, all 52 checked; LawHelp's per-state URLs proved unreliable so it links to LawHelp's own picker; DomesticShelters.org for programs by location): 211 moved to the top of Resources and Emergency; a state `<select>` that deep-links to WomensLaw state page + the Hotline's local search. Static JSON map, no API. | M | U-12 |
| ✅ P2-D9 | Male survivors' path (done 2026-09-26; DAHMW left out because its site was only a placeholder and couldn't be verified): `/for-men.html` (linked from homepage, Resources, and Is-this-abuse; plain title so it isn't conspicuous in history). Covers: it happens to men and it counts; shame and "who would believe me"; fear of being arrested as the aggressor (document everything, call first, what to say to responding officers); custody fears; the fact that most shelters are women-only and what the alternatives are (hotline-arranged hotel stays, the few male-inclusive shelters, staying with family); abuse by female and male partners. Add a men's section to Resources with DV-specific services. Candidates, **each to be verified against its own site before publishing** (project standard): Domestic Abuse Helpline for Men and Women (DAHMW), MaleSurvivor, 1in6 (move out of the population-specific list and also cross-link it here), the National DV Hotline's and RAINN's explicit all-genders statements, and LGBTQ-specific DV services (e.g. the Anti-Violence Project). | M | audience |
| ◐ P2-D8 | (Draft built 2026-09-26: `/es/` home, emergencia, es-abuso, seguridad, recursos; "Español" in every nav; every Spanish-language service verified, e.g. Crisis Text Line is now HOLA not AYUDA. **Native-speaker review still required** before this counts as done.) Spanish crisis path: `/es/` copies of Emergency, Resources, Safety, Is-this-abuse; `lang` attributes; language switch in header; Quick Exit label translated. Machine draft → native-speaking reviewer before publish. | L | U-6 |

| ✅ P2-D11 | Cloudflare Web Analytics (RUM) was injecting a third-party beacon into every page, including `/log.html`, contradicting the privacy statement. Disabled in the dashboard 2026-09-26; runbook now lists it with a one-line check. CSP (P2-A4) will block any recurrence. | S | found in live check |
| ✅ P2-D12 | Stale pages: HTML/CSS/JS had no cache headers, so browsers showed old copies for hours (the owner saw the pre-Phase-2 homepage). Static files now `Cache-Control: no-cache`; private pages stay `no-store`. Committed, **not yet deployed**. | S | found by owner |
| P2-D10 | Put "Is this abuse?" in the primary nav (move Recovery to the footer); it's currently only reachable from the homepage. Owner decision pending. | S | found by owner |

**Deployed 2026-09-26** (`main` at `83d1f08`): D1–D7, D9, the D8 draft, C1, C2 (pending counsel), the interim C5, access logs off. Live probe green on 21 paths.

**Exit gate:** pages live; Spanish reviewed by a native speaker; advocacy reviewer has the new pages in their packet (or a follow-up has been sent).

---

## Sprint 5 — Survivor features and operations

| ID | Ticket | Size | Closes |
|---|---|---|---|
| ✅ P2-E1 | Quick Exit v2 (`shared.js`): `window.open` a neutral site in a new tab **and** `location.replace` the current one; visible "Press Esc twice to leave quickly" hint near the button; test on iOS Safari, Android Chrome, desktop (popup-blocker behaviour differs — the replace must still happen if the open is blocked). | S | U-2 |
| ✅ P2-E2 | Neutral tab titles on private pages (`log.html` → "Notes", `checkin.html` → "Reminders"). | S | U review (Dana #2) |
| ✅ P2-E3 | Notes export: print stylesheet + "Download PDF" generated client-side from decrypted entries (dated, paginated, court-readable). No plaintext request leaves the browser — assert in a test that export makes zero network calls. Client-side search over decrypted entries rides along. | M | U-7 |
| ✅ P2-E4 | Low-key theme: light, neutral, no glow/animation, neutral title; toggle in header; stored in `localStorage` (try/catch); default respects `prefers-reduced-motion`. To meet `DESIGN2.md`'s "works without JS" acceptance, also serve it at `?theme=plain` / a `/plain/` link that a CSS-only page honours, so it works when scripts are blocked. | M | U-11 |
| ✅ P2-E5 | Check-in reliability: stand-down email/push to contacts when the survivor checks in after an alert fired; alert copy numbers repeats ("alert 2"); per-contact "push last confirmed" on `checkin.html`; survivor-visible warning when a contact's push died (from P2-A6 pruning); survivor alert history (new `checkin_alert_log` table, migration `0006`); let the survivor re-invite a contact who self-revoked instead of hitting today's 409 (`TODO.md` rough edge). | M | U-8, TODO items |
| P2-E6 | (Needs real devices and a real Brevo key; checklist in RUNBOOK "Checks that need a real phone".) Real-world check-in verification (still open from `TODO.md`): real push to a real Android + iPhone (home-screen PWA), real Brevo email, alert loop firing on its own timer. Record results in `CHECKIN.md`. | S | TODO |
| ◐ P2-F2 | (Heartbeat ping after each alert pass via `HEALTHCHECK_PING_URL`, and setup steps in RUNBOOK "Monitoring", done 2026-10-02. Owner still has to create the UptimeRobot and Healthchecks.io checks and run the forced test.) Monitoring: UptimeRobot on `/api/health`; Healthchecks.io ping at the end of each alert pass; a missed ping emails/pages a named person. | S | DESIGN2 F |
| ✅ P2-F3 | Abuse alerting: repeated 429s from one IP (e.g. >50/hour) send one email to the operator. | S | TODO |
| ✅ P2-F4 | Dependabot for pip, Docker base image, and GitHub Actions. | S | DESIGN2 F |
| ✅ P2-F5 | `docs/INCIDENT_PLAN.md`: DB breach, host compromise, alert loop outage — who does what, what survivors are told and where. | S | DESIGN2 F |

**Exit gate:** export works on phone and desktop; stand-down verified end-to-end with a real device; monitoring pages someone in a forced test.

---

## Sprint 6 — Close-out

| ID | Ticket | Size | Closes |
|---|---|---|---|
| P2-C7 | Work through legal and advocacy feedback: each item resolved or accepted-with-reason in `docs/legal/` and `docs/advocacy/`. | varies | DESIGN2 §1.4–1.5 |
| ✅ P2-E7 | Photo/screenshot evidence: client-side EXIF strip (re-encode via canvas), client-side encryption, size cap (e.g. 5 MB), `bytea` ciphertext in a new `evidence_attachments` table (migration `0007`). Test that a GPS-tagged JPEG has no EXIF before encryption. Included in export. | L | U review (Marisol #4) |
| ✅ P2-E8 | Encrypted safety plan: the Safety Planning checklist becomes fillable and saves to the vault (reuse `CaseProfile`-style blob or a new one). Included in export. | M | DESIGN2 E |
| ✅ P2-E9 | Installable PWA: manifest, offline cache of Emergency + Resources (+ `/es/` versions) in `sw.js`. | M | DESIGN2 E |
| P2-F6 | Retention policy (after counsel): 18 months inactive, in-app banner warnings at 12 and 17 months, sweep in the maintenance loop. | M | TODO |
| P2-B10 | Reopen signups (flip `BETA_SIGNUPS_ENABLED`) **only** if C3 + C4 are resolved. Remove `X-Robots-Tag` and `robots.txt` block at the same time if launching publicly. | S | H6 |
| — | Check off the ten "done" conditions in `DESIGN2.md` §1 with the commit for each, and freeze that file. | S | — |

---

## 3. Migration ledger

Migrations are sequenced so each ships with the sprint that needs it. After P2-A15 they run as an explicit deploy step, not on container start.

| Rev | Sprint | Change |
|---|---|---|
| 0003 | 1 | `users.evidence_key_check_ciphertext`, `users.evidence_key_check_iv` |
| 0004 | 1 | `push_subscriptions`: drop unique(`endpoint`), add unique(`trusted_contact_id`, `endpoint`) |
| 0005 | 2 | `recovery_codes.code_sha256` (+ index) |
| 0006 | 5 | `checkin_alert_log` table |
| 0007 | 6 | `safety_plans` and `evidence_attachments` tables |
| 0008 | 6+ | drop `users.failed_login_count`, `users.locked_until` (after one release on P2-A5) |

If P2-A7 uses invite codes stored in the DB rather than an env setting, it takes the next free revision in Sprint 1.

## 4. Test plan summary

| Layer | What | Where |
|---|---|---|
| Unit / API | auth, lockout, recovery, sessions, evidence ownership, key-check storage, invite tokens, subscriptions, schedule math, overdue, advisory lock, startup checks | `backend/tests/` (pytest + Postgres service) |
| Client crypto | derive / encrypt / decrypt / wrong key / key-check / export makes no network calls | `html/tests/` (`node --test`) |
| Edge | security headers incl. HSTS + CSP on every page and `/api/*` | `scripts/probe_headers.sh` in CI against built nginx |
| Live | page 200s + headers + `/api/health` after every deploy | `scripts/smoke.sh https://solusvires.com` |
| Manual (recorded) | Quick Exit on three browsers; real push on Android + iPhone; real Brevo email; export on phone | checklists in `RUNBOOK.md` / `CHECKIN.md` |

## 5. Risks to this plan

| Risk | Mitigation |
|---|---|
| External reviews (legal, advocacy) take months | Request them in Sprint 3, not at the end; H6 gate stays closed until they return, so nothing unsafe waits on them |
| In-process rate limiter/lockout resets on restart and won't scale past one worker | Accepted for Phase 2 and documented in the threat model; Redis only if a second worker is ever added |
| H3 backfill can't verify a PIN for users who set a PIN but saved nothing | Treat as fresh setup (enter twice); there is no data to lose in that state |
| CSP breaks a page silently | Probe + a manual click-through checklist; ship `Content-Security-Policy-Report-Only` for one deploy first |
| PBKDF2 at 600k iterations takes 1–3 s on older phones (L6) | Accepted for Phase 2; show a "Unlocking…" state so it doesn't look frozen (in P2-A10). Argon2id via WASM is noted for Phase 3 |
| Scope creep from the "not in Phase 2" list | `DESIGN2.md` §5 is the fence: location sharing, SMS, MFA, partner portal, native apps, full disguise stay out |

## 6. Guardrails: what not to "improve"

These come from the user review and `DESIGN2.md` §2. Any ticket that would change one of them needs an explicit decision in section 1 first.

- The honesty about limitations. Don't soften it, including on the new About and Privacy pages.
- Browsing stays account-free. No email or phone number at signup.
- The Recovery page's tone.
- The verified-resources standard. Every new link, number, and claim is checked against its source.
- No registry, ever.
- No third-party scripts, fonts, or trackers (this is why CAPTCHA is deferred, D7).
- Every survivor-facing feature stays opt-in, visible, revocable, and off by default.
- For every gender. No copy assumes the survivor is a woman or the abuser is a man. Pronouns stay neutral ("they", "your partner") unless a page is deliberately addressed to one group, like `/for-men.html`. New content is checked against this before merge.

## 7. Keeping this file honest

- When a ticket starts, mark it `▶` next to its ID; when done, `✅` plus the commit hash. Ticket status lives here, and `TODO.md` points here for Phase 2 items instead of duplicating them (`DESIGN2.md` §7 updated to match). `PROGRESS.md` stays the only "what exists now" page and gets a one-line summary at each sprint exit.
- New findings get a new ticket ID in the right sprint rather than being slipped into an existing one.
- When Sprint 6 closes, this file is frozen alongside `DESIGN2.md`.

---

## Appendix A — Coverage matrix

### Engineering review
| Finding | Ticket | | Finding | Ticket |
|---|---|---|---|---|
| H1 Cloudflare IP | P2-A1 | | M6 Recovery CPU | P2-A13 |
| H2 Headers | P2-A2, P2-B5 | | M7 Sessions | P2-A14 |
| H3 PIN fork | P2-A3, P2-B6 | | M8 Compose | P2-A15 |
| H4 Push reassignment | P2-A6 | | M9 Empty secret | P2-A16 |
| H5 Lockout abuse | P2-A5 | | M10 Tests/CI/pins | P2-B1–B4, B6 |
| H6 Live sign-ups | P2-A7 (D1), P2-B10 | | L1 SameSite | P2-A17 |
| M1 Double alert loop | P2-A8 | | L2 HSTS/CSP | P2-A2, P2-A4 |
| M2 Timing enumeration | P2-A9 | | L3 Dead deploy config | P2-B8 |
| M3 PIN floor | P2-A10 (D5) | | L4 `.DS_Store` | P2-B8 |
| M4 Deadline | P2-A11 | | L5 Docs drift | P2-B9 |
| M5 Email fallback | P2-A12 (D4) | | L6 PBKDF2 speed | §5 risk (Phase 3) |
| | | | L7 Robots meta | P2-A2 |

Process asks: smoke probe → P2-B5/B7 · fail-closed config → P2-A1, A16 · docs "verified against commit" → P2-B9 · deployment story → P2-B8 · backup + restore → P2-F1.

### User review ("fix this month" table)
| # | Ticket | | # | Ticket |
|---|---|---|---|---|
| U-1 About + privacy | P2-C1, C2 | | U-7 Notes export | P2-E3 |
| U-2 Quick Exit | P2-E1 | | U-8 Alert page + stand-down | P2-D5, E5 |
| U-3 Hero copy | P2-D1 | | U-9 Nav/"tracked" | Sprint 1 ride-along |
| U-4 Is this abuse? | P2-D2 | | U-10 Contact form | P2-C5 (D3) |
| U-5 Safety planning | P2-D3 | | U-11 Low-key theme | P2-E4, E2 |
| U-6 Spanish | P2-D8 | | U-12 Local finder | P2-D7 |

Audience (added after review, not a review finding): men and all genders → D9, P2-D1, D2, D4, D6, D9, C4, §6 guardrail.

Persona findings outside the table: Dana #5 (nav crowding) → Sprint 1 ride-along; done 2026-10-01: on phones the links collapse behind a menu button in the header (`html/shared.js` + `html/shared.css`), Quick Exit stays on the one-row header · Marisol #4 (photos) → P2-E7 · Marisol #5 (PIN warning timing) → P2-A10 · Marisol #6 (legal depth) → P2-D6 · Jo #1 (is this phishing?) → P2-C1, D5 · Jo #3 (repeats, stand-down) → P2-A12, E5 · Jo #4 (push breaks) → P2-A6 · Priya #1 (terms) → P2-C2 · Priya #3 (live sign-ups) → P2-A7 · Priya #4 ("tracked") → Sprint 1 · Priya #5 (help someone) → P2-D4 · Priya #6 (populations) → P2-D3b.

### `DESIGN2.md` §1 "done" conditions
1 → Sprints 1–2 · 2 → P2-B4 · 3 → P2-C1, C2, C5 · 4 → P2-C3, C7 · 5 → P2-C4, C7 · 6 → P2-D1–D4, D8, D9 · 7 → P2-E3, P2-A3 · 8 → P2-D5, E5, A6 · 9 → P2-F1, F2 · 10 → P2-A7, B10.

### `TODO.md` open items
Legal / threat model / advocacy → P2-C3, C6, C4 · real push, Brevo, iOS, natural timer → P2-E6 · tell survivor when push dies → P2-A6, E5 · CAPTCHA → D7 (deferred) · abuse alerting → P2-F3 · backup/restore → P2-F1 · retention → P2-F6 · audit logging → D8 / P2-C6 · MFA, location sharing, partner tooling, full disguise → out of Phase 2 per `DESIGN2.md` §5 · photo upload → P2-E7 · re-invite after self-revoke → P2-E5 · alert history → P2-E5.
