# Engineering Review — Solus Vires

**Reviewer role:** Senior software engineering manager
**As of:** 2026-09-26, branch `dev` at `e175ccf`
**Scope:** Everything in the repo, plus a read-only probe of the live site (`https://solusvires.com`) to confirm deployment shape and response headers. No code was changed.

---

## Verdict

This is an unusually well-reasoned prototype. The safety instincts are right (no email/SMS recovery, client-side encryption, opaque revocable sessions, consent-first invites, refusing to build an abuser registry), the docs are honest about what is and is not verified, and the code is small and readable. I would be happy to have this as the starting point for a real product.

It is not yet something a survivor should be told to rely on, and the gap is not "more features." The gap is:

1. **Six specific defects that undermine the safety promises already made** (below, marked High). Three of them are in the live deployment right now.
2. **No automated tests, no CI, no dependency pinning.** Every "verified end-to-end" claim in the docs is a one-time manual run that nobody can repeat.
3. **The live site accepts real accounts today**, while the project's own docs say legal review, a threat model, and advocacy input are hard prerequisites for that.

Fix the High items, add a test harness, and gate real sign-ups, and this moves from "impressive prototype" to "credible beta."

---

## What is genuinely good

- **The threat model is baked into the design, not bolted on.** Username-only accounts, one-time recovery codes shown once, a separate Notes PIN with no recovery path, generic "Notes" labelling, `no-store` on private pages, auto-lock on tab hide. These are the choices an experienced DV-tech reviewer would ask for.
- **Zero-knowledge notes are real, not marketing.** `backend/app/models/evidence.py` has no plaintext column at all. `html/evidence-crypto.js` derives a non-extractable AES-GCM key in the browser. The server cannot read notes even if compelled.
- **Sessions are opaque and revocable.** `backend/app/core/security.py` stores SHA-256 of a random token; `logout-all` deletes rows. Choosing this over JWT for instant revocation is the correct call for this audience.
- **The invite-token design is sound.** The HMAC-signed capability link in `backend/app/services/checkin.py` is stateless, regenerable, and compared in constant time.
- **Notifications fail soft.** Unconfigured push/email log and return rather than raise, so the request path never breaks because plumbing is missing.
- **The docs are honest.** `PROGRESS.md` and `TODO.md` distinguish "verified against the live stack" from "only exercised with a fake endpoint." That is rare and valuable. Keep it.
- **No third-party scripts, fonts, or trackers.** For a site people visit on monitored devices, that is a feature.

---

## Findings

Severity reflects impact on a survivor, not code aesthetics.

### High

**H1. Rate limiting is keyed on Cloudflare's IP, not the visitor's.**
`backend/app/core/rate_limit.py:23-29` trusts `X-Real-IP`, which `nginx/conf.d/default.conf` sets from `$remote_addr`. The live site is proxied by Cloudflare (confirmed: `server: cloudflare`, `cf-ray` header, and `certs/origin.crt` is a Cloudflare Origin CA cert). So `$remote_addr` is a Cloudflare edge IP shared by many visitors.
*Effect:* Everyone routed through the same edge shares one bucket. Login is 20 per 5 minutes. A handful of legitimate users, or one attacker, locks out login and registration for everyone. Meanwhile the attacker is not actually limited per their own address.
*Fix:* In nginx, `set_real_ip_from` the published Cloudflare ranges and `real_ip_header CF-Connecting-IP`, then keep passing `X-Real-IP $remote_addr`. In the app, only honour proxy headers when a `TRUST_PROXY_HEADERS=true` setting is on, so a bare `uvicorn` never trusts a client-supplied header.

**H2. The most sensitive pages are served without the security headers.**
In `nginx/conf.d/default.conf`, the `location ~ ^/(account|log|checkin|checkin-invite)\.html$` block adds `Cache-Control` with its own `add_header`. In nginx, any `add_header` in a location replaces all inherited ones. Verified live: `/` returns `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, and `X-Robots-Tag`; `/log.html` returns only `cache-control`.
*Effect:* The account, notes, and check-in pages can be framed (clickjacking), are not marked `noindex` at the header level, and leak full referrers. These are exactly the pages the pre-launch `noindex` was meant to protect.
*Fix:* Move the header set into a snippet and `include` it in every location, or repeat the four headers (with `always`) inside that block. Add a header test to CI (curl each page, assert headers).

**H3. A wrong PIN can silently fork the notes vault.**
`html/log.html` `verifyKey()` proves the key by decrypting the case profile or the first entry. If the PIN has been set but nothing has been saved yet, any PIN is accepted ("a first-ever unlock is allowed through unverified"). The survivor then writes entries under a key derived from the wrong PIN. Later, the correct PIN shows those entries as "Unable to decrypt," and the wrong PIN shows the others the same way. `ACCOUNTS_AND_NOTES.md` records the earlier wrong-PIN bug as fixed; this is the remaining hole in the same flow.
*Effect:* Permanent, unrecoverable loss of evidence, in the feature whose whole promise is "only you can read this."
*Fix:* At PIN setup, encrypt a known constant (a key-check blob) and store it alongside the salt. Verify against that on every unlock. One extra column, one migration.

**H4. A trusted contact's push device can be silently reassigned.**
`backend/app/services/checkin.py` `add_subscription()` treats `endpoint` as globally unique and re-points an existing row to whichever contact subscribed last. A browser holds one push subscription per origin. A person who is the trusted contact for two survivors will have their device moved to the second survivor's invite, and the first survivor's contact card drops to "0 devices" with no notification to anyone.
*Effect:* A safety alert channel stops working without either party being told. This is the "false negative" risk `TODO.md` already worries about, and it is reachable today.
*Fix:* Model a device (endpoint, keys) separately from the contact link, many-to-many. Or at minimum key uniqueness on `(trusted_contact_id, endpoint)` and let the same endpoint appear under several contacts.

**H5. Per-account lockout gives an abuser a denial-of-access button.**
`backend/app/core/security.py`: 8 failed logins lock the account for 15 minutes, keyed on the account alone. Anyone who knows the username, which includes every trusted contact (the invite page shows it) and anyone who has glanced at the survivor's screen, can lock the survivor out of Notes and check-ins indefinitely by retrying every 15 minutes, from anywhere.
*Effect:* Turns a security control into a harassment tool against the person it is meant to protect.
*Fix:* Lock on `(client IP, username)` pairs, use progressive delay rather than a hard lock, and let a valid recovery code bypass the lock. Never hard-lock an account on username alone.

**H6. The production stack is live and accepting sign-ups ahead of the project's own gates.**
`https://solusvires.com/account.html` serves the registration form and `/api/health` answers. `noindex` is set, but the URL is shareable and search engines are not the only way people find things. The README says legal review, a threat model, and advocacy input are hard prerequisites before real-world use. This is a management finding, not a code one.
*Fix:* Either put registration behind an invite code / `BETA_SIGNUPS_ENABLED` flag, or show a plain banner on `account.html`: "Prototype. Not yet reviewed by legal counsel or an advocacy organization. Do not rely on this for your safety." Pick one this week.

### Medium

**M1. Two alert loops can run against the same database.**
`PROJECT_REPORT.md` section 9 makes the local `uvicorn` and the Docker `api` container share one Postgres on purpose. Each process starts its own `run_alert_loop()`. Run both and every overdue survivor's contacts get double alerts each cycle. This is real today, not a future multi-replica concern.
*Fix:* Wrap `run_due_alerts_once()` in `pg_try_advisory_lock`, and/or default `CHECKIN_ALERT_LOOP_ENABLED=false` outside Docker.

**M2. Username enumeration by timing.**
`backend/app/services/auth.py` `login()`: an unknown username returns immediately; a known one runs Argon2 (tens to hundreds of ms). Usernames are chosen to be non-identifying, which softens this, but it is still a free oracle for "does this username exist."
*Fix:* Verify against a static dummy hash when the user is not found.

**M3. The Notes PIN floor is too low for the threat model.**
`log.html` accepts a 6-character PIN. A six-digit numeric PIN is 10^6 guesses. With the ciphertext and salt in the database, an attacker who obtains a DB dump (the exact scenario zero-knowledge is meant to survive) brute-forces 600k-iteration PBKDF2 over 10^6 candidates in hours on a laptop. The copy says "10+ characters recommended"; the code enforces 6.
*Fix:* Enforce 12+ characters or a short passphrase, show a strength hint, and say plainly that the PIN is the only thing standing between a stolen database and the notes.

**M4. Changing the check-in interval while active does not move the deadline.**
`services/checkin.py` `update_schedule()` recomputes `next_deadline_at` only when activating. Shortening 1 week to 12 hours leaves the old deadline in place for up to a week.
*Fix:* Recompute `next_deadline_at = last_checkin_at + interval` on every save while active.

**M5. Email is not a fallback; it always sends.**
`CHECKIN.md` and the README describe email as the fallback when push fails. `_alert_contacts_for()` sends push to every device and then always emails. Fine as a product choice, but the docs describe different behaviour, and every 6-hour repeat re-emails. Decide which is intended and make the docs match.

**M6. Recovery code check is a cheap CPU-exhaustion target.**
`recover()` runs up to 10 Argon2 verifications per request. The 10/hour/IP limit is currently keyed on Cloudflare IPs (H1). Recovery codes are 80 bits of randomness; they do not need a memory-hard hash.
*Fix:* Store a SHA-256 (with a per-user pepper) for recovery codes and look up by hash, or drop Argon2 cost for this table.

**M7. Expired sessions are never purged, and every authenticated request writes.**
`get_current_user()` commits `last_seen_at` on every call. The `sessions` table grows forever.
*Fix:* Only update `last_seen_at` if older than a few minutes. Sweep expired rows in the existing background loop.

**M8. The production compose file bind-mounts source and runs migrations on every start.**
`docker-compose.yml` mounts `./backend/app` into the container while setting `APP_ENV=production`, bypassing the built image, and runs `alembic upgrade head` unconditionally in `CMD`.
*Fix:* Move the bind mount to `docker-compose.override.yml` (already gitignored). Run migrations as an explicit step, not on every container start.

**M9. A missing `CHECKIN_TOKEN_SECRET` only logs a warning.**
`main.py` warns and continues with an empty HMAC key. Invite and alert links are then forgeable by anyone who knows a contact UUID.
*Fix:* Refuse to start when `APP_ENV=production` and the secret is empty. Same for `POSTGRES_PASSWORD` defaults.

**M10. No tests, no CI, no lint, unpinned dependencies, mismatched Python.**
Zero test files. `requirements.txt` has no versions. The venv is Python 3.14; the Dockerfile is 3.12. There is no `pyproject.toml`, no `ruff`, no `.github/workflows`. The crypto round-trip, the HMAC token parser, the lockout logic, and `is_overdue()` are all pure functions that would take an afternoon to cover.
*Fix:* `pytest` + `httpx` `TestClient` against a throwaway Postgres in CI. Start with: token sign/verify, register/login/lockout, evidence CRUD ownership, `is_overdue`, and a curl-based header check against nginx.

### Low

- **L1.** `SameSite=Strict` means a survivor arriving from any external link (email, text, another site) lands with no cookie and sees "You need to be logged in" until they reload. `Lax` is safe here: all state-changing routes are JSON `POST/PUT/DELETE` with no CORS middleware, so cross-site requests cannot reach them. (`/api/contact` is form-encoded and technically CSRF-able, but it does nothing.)
- **L2.** Missing `Strict-Transport-Security` and `Content-Security-Policy` everywhere. HSTS is one line. CSP needs the three inline `<script>` blocks (`account.html`, `log.html`, `contact.html`) moved to files first.
- **L3.** Two deployment configs, one dead: `wrangler.jsonc` and `html/_redirects` describe a static-only Cloudflare deploy that cannot serve `/api/*`. `_redirects` is also missing the newer pages. Delete or document.
- **L4.** `.DS_Store` files sit in `backend/` and `nginx/` on disk (correctly gitignored, not committed). Harmless, but a `find . -name .DS_Store -delete` keeps them out of the Docker build context.
- **L5.** Docs drift: `ARCHITECTURE.md` says "no rate limiting"; `TODO.md` says it is done. README calls the current state "Phase 1 plus an early Phase 2 feature"; `PROGRESS.md` calls Phase 2 done. One source of truth.
- **L6.** PBKDF2 at 600k iterations takes 1-3 seconds on older phones. Acceptable now; note Argon2id via WASM as a later option.
- **L7.** `X-Robots-Tag` and `robots.txt` block indexing, but `checkin.html` also has a `<meta name="robots">` while `log.html` and `account.html` do not. Consistency only, since H2 is the real problem.

---

## Process and team observations

- **Manual verification is doing the job of tests.** The verification logs in `CHECKIN.md` are excellent as a test plan. Turn them into `pytest` cases so they run on every push instead of once.
- **Security-critical config fails open.** Empty secrets warn, dev cookie flags default insecure, proxy headers are trusted unconditionally. Flip the defaults: production refuses to start when misconfigured.
- **The docs are the strongest asset. Protect them from drift.** Add a "last verified against commit X" line to each doc, and delete `PROJECT_REPORT.md` claims that are superseded rather than layering new docs on top.
- **The nginx location-block header bug (H2) is the kind of thing only a probe catches.** Add a five-line smoke script that curls every page on the live site and asserts headers. Run it after every deploy.
- **Decide the deployment story.** Cloudflare proxy in front of a single Docker host is fine, but write it down: what the origin is, how certs rotate (the origin cert is valid to 2040, so effectively never), how backups run (they do not yet), and who gets paged (nobody yet).

## What I would ask for before the next sprint

1. H1 through H6 fixed and probed on the live site. Roughly one focused week.
2. A test harness with the first ten tests and CI running them. One to two days.
3. A written decision on H6: invite-gated beta, or a visible prototype banner.
4. A backup taken and a restore rehearsed, once, on the real Postgres volume.

The Phase 2 plan in `DESIGN2.md` sequences all of this.
