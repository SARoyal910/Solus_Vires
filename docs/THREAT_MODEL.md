# Threat model

**Last verified against:** branch `lane/c` off `phase2` at `83be254`, plus Lane A's work on branch `lane/a` (2026-10-02), by reading the code, not the docs.
**Ticket:** P2-C6. Records decisions D7 (CAPTCHA), D8 (audit logging) and the MFA deferral.
**Scope:** the public site, accounts, the encrypted Notes vault, check-ins and trusted contacts, and the production deployment (Cloudflare → DigitalOcean droplet → nginx / FastAPI / Postgres).

This is a working document. Every mitigation below names the file that implements it and the test that proves it. Where a mitigation is being built today by another ticket, it says **lands with P2-xx** and must not be read as done. If you change one of the named files, check the matching row here.

Status marks: **✅** in the code and covered by an automated test · **✅ lane/a** done and tested on branch `lane/a` (2026-10-02), not yet merged into `phase2`; test files are under `backend/tests/` on that branch · **◐** in the code, checked by hand or only partly tested · **⏳ lands with P2-xx** in flight, not yet merged · **✗** accepted risk or known gap (reasoning given).

---

## 1. What we are protecting

| Asset | Why it matters | Where it lives |
|---|---|---|
| **What the survivor wrote** (notes, case profile) | Evidence; can be used against them if read by the abuser | Ciphertext only: `evidence_entries`, `case_profiles` (`backend/app/models/evidence.py`) |
| **The fact that someone uses the site** | Being seen looking for help can trigger escalation | The survivor's device and browser; Cloudflare; not in our logs |
| **The survivor's support network** (trusted contacts' emails) | An abuser who learns who the survivor would turn to can isolate or threaten them | Plaintext: `trusted_contacts.contact_email` |
| **The survivor's routine** (check-in schedule and times) | Reveals when they're expected to be OK, and when they're not | Plaintext: `checkin_schedules` |
| **The alert channel working** | A silent failure is a false sense of safety | Push subscriptions, Brevo, the alert loop in `backend/app/services/checkin.py` |
| **The survivor's own access** | Being locked out of their notes or check-ins is itself harm | Login throttle, recovery codes |

Not collected at all, by design: real names, phone numbers, location, email of the survivor, IP history, page-view history.

## 2. Actors

| # | Actor | Wants | Can |
|---|---|---|---|
| A1 | **Abuser with access to the device** | See whether the survivor is seeking help; read notes; find contacts | Pick up an unlocked phone or laptop; look at history, tabs, saved passwords, site data; possibly install monitoring software |
| A2 | **Abuser who knows the username** (and maybe the password) | Get into the account; lock the survivor out; delete evidence; learn contacts | Try passwords from anywhere; use any password the survivor has reused; read an invite email that shows the username |
| A3 | **Whoever gets a copy of the database** (breach, stolen backup, careless operator) | Read notes; identify users and contacts | Run offline guessing at any speed they can afford |
| A4 | **A hostile or careless trusted contact** | Learn about the survivor; ignore alerts; pass information to the abuser | Hold the invite link; see the survivor's username and alerts |
| A5 | **Legal compulsion** (subpoena, court order, discovery in a custody case) | Whatever records exist about a user | Compel the operator, DigitalOcean, Cloudflare, or Brevo to hand over what they hold |
| A6 | **Our providers** (Cloudflare, DigitalOcean, Brevo, browser push services), or someone who compromises them | Varies | Cloudflare terminates TLS and can rewrite pages; DigitalOcean holds the disk; Brevo sees alert emails |
| A7 | **Anyone on the internet** | Spam, credential stuffing, denial of service, defacement | Send any request at volume |

The operator is inside A5 and A6's blast radius on purpose: the design goal is that the operator *cannot* hand over or leak what the operator never had.

## 3. Mitigations by actor

### A1 · Abuser with access to the device

| Mitigation | Implemented in | Proven by | Status |
|---|---|---|---|
| Reading the site needs no account, sets no cookie of ours, and loads no third-party script, font or tracker | `html/*`; session cookie only set at login (`backend/app/core/security.py` `create_session`) | `scripts/smoke.sh` step 5 (no third-party `<script src>`, no Cloudflare beacon) | ◐ smoke runs after deploy, not in CI yet |
| Private pages are never stored in the browser cache | `nginx/conf.d/default.conf` (`no-store` location), `backend/app/core/middleware.py` | `scripts/smoke.sh` step 4 | ◐ |
| Quick Exit: button and double-Escape replace the page with weather.com | `html/shared.js` `quickExit()` | Manual | ◐ Back button and history still show the visit. Opening a decoy tab and a visible hint **lands with P2-E1** |
| Notes are locked behind a separate PIN that never leaves the browser; the derived key is non-extractable | `html/evidence-crypto.js` (`deriveKey`, `extractable=false`), `html/log.html` | `tests/web/crypto.test.mjs` | ✅ |
| Notes lock after 4 minutes idle and whenever the tab is hidden | `html/log.html` (`AUTO_LOCK_MS`, `visibilitychange`) | Manual | ◐ |
| Neutral labels: the vault is "Notes", the nav says "Notes & Check-ins" | `html/log.html` `<title>`, nav in every page | Review | ◐ Neutral titles on every private page **land with P2-E2**; the low-key theme **lands with P2-E4** |
| No email or phone at sign-up, so no reset message lands in a shared inbox | `backend/app/schemas/auth.py` (username + password only) | `backend/tests/test_auth.py` | ✅ |
| Every session can be ended at once from any device | `POST /api/auth/logout-all` (`backend/app/services/auth.py`) | `test_logout_all_ends_every_session` | ✅ |
| The installable app and offline copy are opt-in, plainly named, and removable; no install prompt; private pages and `/api/` are never cached | `html/manifest.json`, `html/sw.js`, `html/offline.js`, the install-banner block at the end of `html/shared.js` | `tests/browser/offline.mjs` (21 checks, also in CI) | ✅ (P2-E9) |

**What remains (✗):** anything installed on the device (stalkerware, a keylogger, screen recording) sees the PIN as it's typed; no web page can defend against that. Browser history, a saved password, and an open session are visible to whoever holds the unlocked device. The Recovery page keeps exercise progress in `localStorage` (disclosed on `/privacy.html`). The site says this plainly on `log.html` and `safety.html`; that honesty is the mitigation.

### A2 · Abuser who knows the username

| Mitigation | Implemented in | Proven by | Status |
|---|---|---|---|
| Failed logins slow only the guessing (IP, username) pair; nobody can lock the survivor out (H5) | `backend/app/core/login_throttle.py`, `backend/app/services/auth.py` `login` | `test_failed_logins_never_lock_the_owner_out_from_elsewhere`, `test_guessing_pair_is_slowed_down`, `test_delay_grows_and_is_capped` | ✅ |
| A valid recovery code always works, even while throttled | `services/auth.py` `recover`, `login_throttle.forget_username` | `test_recovery_code_works_while_throttled_and_clears_the_wait`, `test_recovery_code_resets_password_once_and_ends_sessions` | ✅ |
| Per-IP request limits on login (20/5 min), register (5/h), recovery (10/h), invites (30/5 min), keyed on the real visitor IP (H1) | `backend/app/core/rate_limit.py`, `nginx/snippets/cloudflare-realip.conf` | `backend/tests/test_rate_limit.py`, `test_register_is_rate_limited_per_ip` | ✅ |
| Same error for unknown user and wrong password | `services/auth.py` `login` | `test_wrong_password_and_unknown_user_get_the_same_error` | ✅ |
| Same *timing* for unknown user and wrong password (M2): an unknown username is verified against a dummy Argon2 hash | `services/auth.py` `_DUMMY_PASSWORD_HASH` | `test_login_timing.py` (`test_unknown_username_runs_a_dummy_verify`, `test_unknown_and_wrong_password_take_comparable_time`) | ✅ lane/a (P2-A9) |
| Registration can't be used to test whether a username exists without an invite code | `services/auth.py` `check_signup_allowed` runs before the username lookup | `backend/tests/test_signup_gate.py` | ✅ |
| Notes stay unreadable even with the password: the PIN is separate | `html/log.html`, `html/evidence-crypto.js` | `tests/web/crypto.test.mjs` | ✅ |
| Session cookie is `HttpOnly`, `Secure` in production, `SameSite=Lax` (so a survivor arriving from an email link is still signed in) | `core/security.py` `create_session`; `SESSION_COOKIE_SECURE=true` in `docker-compose.yml` | `test_sessions.py::test_session_cookie_is_samesite_lax_httponly` | ✅ lane/a (P2-A17; `Strict` on `phase2`) |
| Expired sessions are deleted, and `last_seen_at` is written at most every 5 minutes | `core/security.py` `sweep_expired_sessions`, `LAST_SEEN_RESOLUTION` | `test_sessions.py` | ✅ lane/a (P2-A14) |

**What remains (✗), and what we recommend:**
- Someone who has the **password** can see the contact list and schedule, turn check-ins off, end the survivor's sessions, delete notes (deleting needs a session, not the PIN), or delete the whole account (needs the password, which they have). The server cannot ask for the PIN, because it never learns it. Encrypted backups keep deleted data for up to 30 days, but there is no per-user restore. *Recommendation (new ticket):* show the survivor where they're signed in (count and last-seen times, no IPs) and offer a short undo window for deleted notes.
- Someone who finds the written-down **recovery codes** can take the account over: a recovery ends every session and sets a new password. This is the trade-off of any offline recovery code; the sign-up screen (`html/account.html`) says to keep them "somewhere the person hurting you cannot find, not in a shared cloud account or a device they can access".

### A3 · Whoever gets a copy of the database

| Mitigation | Implemented in | Proven by | Status |
|---|---|---|---|
| Notes and case profile are AES-256-GCM ciphertext; the key comes from the PIN via PBKDF2-SHA256, 600,000 iterations, random 16-byte salt | `html/evidence-crypto.js`; no plaintext column in `backend/app/models/evidence.py` | `tests/web/crypto.test.mjs` ("ciphertext never contains the plaintext", wrong PIN fails) | ✅ |
| New PINs must be at least 12 characters (D5), so offline guessing of a stolen vault is expensive | `html/log.html` (`minlength="12"` and the setup check) | `tests/browser/notes_pin.mjs` ("PIN under 12 characters is refused"), run by hand | ◐ Strength hint, "only thing protecting your notes" copy and re-prompt for older short PINs **land with P2-A10** |
| Passwords hashed with Argon2id (argon2-cffi defaults: t=3, 64 MiB) | `core/security.py` `hash_secret` | `backend/tests/test_auth.py` | ✅ |
| Session tokens stored only as SHA-256, so a stolen table yields no usable cookie | `core/security.py` `_hash_token` | `test_login_sets_httponly_session_cookie_and_me_works` (round trip) | ◐ no test asserts the raw token is absent from the table |
| Recovery codes stored as HMAC-SHA256 keyed with `RECOVERY_CODE_PEPPER`, which lives in `.env`, not the database, so a dump alone can't test guesses; one indexed lookup instead of up to ten Argon2 checks (M6). Codes issued before migration 0005 keep their Argon2 hash until used | `core/security.py` `recovery_code_digest`, `services/auth.py` `recover`, migration `0005` | `test_recovery_codes.py` | ✅ lane/a (P2-A13) |
| Invite links can't be forged from the database alone: they're HMACs under `CHECKIN_TOKEN_SECRET`, which lives in the droplet's `.env`, not the database | `services/checkin.py` `_sign`, `_parse_contact_token` | `test_contact_token_round_trips`, `test_tampered_contact_tokens_are_rejected` | ✅ |
| Production refuses to start with an empty or placeholder `CHECKIN_TOKEN_SECRET` or `RECOVERY_CODE_PEPPER`, or a default database password (M9); `scripts/deploy.sh` checks the same before building | `core/config.py` `production_config_problems`, `main.py` lifespan | `test_startup_checks.py` | ✅ lane/a (P2-A16) |
| Backups are encrypted to an `age` public key before they touch disk; the private key is offline | `scripts/backup.sh` | Restore rehearsal logged in `docs/RUNBOOK.md` (2026-09-26) | ◐ manual, by design |
| Postgres is reachable only on loopback | `docker-compose.yml` (`127.0.0.1:5433`) | Review | ◐ |

**What remains (✗):** the database holds in plaintext what `/privacy.html` lists: usernames, contacts' nicknames and emails, schedules and check-in times, push endpoints, account and note timestamps, and how many notes exist. A thief learns *who a survivor's contacts are* and *when they check in*. Encrypting those would break alerts (the server must read the email address to send to it). Notes protected by a short pre-D5 PIN remain guessable until P2-A10 prompts a change. What to do if this happens: `docs/INCIDENT_PLAN.md`.

### A4 · A hostile or careless trusted contact

| Mitigation | Implemented in | Proven by | Status |
|---|---|---|---|
| A contact sees only the survivor's username, the invite status and the device count, never the nickname the survivor gave them, the schedule, other contacts, or notes | `backend/app/schemas/checkin.py` `InviteInfoResponse` | `test_invite_link_flow` | ✅ |
| Nothing is sent until the contact accepts | `services/checkin.py` `accept_invite`, `_alert_contacts_for` (accepted contacts only) | `test_invite_link_flow` | ✅ |
| The contact can stop alerts at any time; the survivor can remove a contact at any time and sees each contact's status | `services/checkin.py` `stop_invite`, `remove_contact`; `html/checkin.html` | Review (no test calls `stop` or the contact `DELETE` yet) | ◐ |
| One phone can serve several survivors without one silently losing the device (H4) | Migration `0004`; `services/checkin.py` `add_subscription` | `test_one_phone_can_be_the_contact_for_two_survivors`, `test_resubscribing_is_idempotent_and_refreshes_keys_everywhere`, `test_expired_device_is_removed_for_every_contact` | ✅ |
| The survivor sees when each contact's push last worked and when it was lost; alerts are numbered; contacts get a stand-down when the survivor checks in or turns check-ins off; the survivor has an alert history (counts only, 90 days, clearable); a contact who stopped can be invited again | `services/checkin.py`, migration `0006` | `test_checkin_reliability.py` | ✅ lane/a (P2-E5) |
| Contacts are told what to do and what not to do (don't confront the partner) | `html/if-you-get-an-alert.html`, linked from every alert | `test_alerts_point_contacts_to_guidance` | ✅ |

**What remains (✗):** a contact learns the survivor's username, which is why H5 (no username lockout) mattered. The invite link never expires; anyone the contact forwards it to can accept or stop alerts. A contact who chooses not to act can't be made to, and `checkin.html` doesn't yet say so in as many words (see §6).

### A5 · Legal compulsion

What could and couldn't be handed over is stated, in plain words, on `/privacy.html` ("If someone demands your data"). It stays true because of these:

| Mitigation | Implemented in | Proven by | Status |
|---|---|---|---|
| No access logs: nothing records which IP opened which page | `nginx/conf.d/default.conf` (`access_log off`), `backend/Dockerfile` (`--no-access-log`) | Review; owner check on the droplet in `docs/TODO.md` | ◐ |
| App logs name events, never content or usernames (`account_login`, `checkin_alerts_sent`) | `backend/app/services/*.py` | Review | ◐ |
| Docker logs are size-capped (10 MB × 3) | `docker-compose.yml` `x-logging` | Review | ◐ |
| IPs are held only in memory, for rate limiting and the login throttle | `core/rate_limit.py`, `core/login_throttle.py` | Review | ◐ |
| The operator cannot decrypt notes | `html/evidence-crypto.js` | `tests/web/crypto.test.mjs` | ✅ |
| Contact-form messages are emailed to the operator's inbox through Brevo and never stored or logged by the site | `services/contact.py` | `test_contact.py` (`test_nothing_is_stored`, `test_message_text_never_reaches_the_logs`) | ✅ lane/a (P2-C5) |
| Check-in alert history is counts only and swept after 90 days | `services/checkin.py` `ALERT_LOG_RETENTION` | `test_old_alert_history_is_swept` | ✅ lane/a (P2-E5) |
| Inactive accounts deleted on a schedule | — | — | ⏳ lands with P2-F6 (after counsel) |

**What remains (✗):** contact-form messages sit in the operator's email inbox, outside the site's control and its "nothing stored" guarantee; that inbox is now a place a subpoena or a mailbox breach could reach (stated on `/privacy.html`). Counsel's questions (mandatory reporting, responding to a subpoena) are in `docs/legal/` (P2-C3).

### A6 · Our providers

| Mitigation | Implemented in | Proven by | Status |
|---|---|---|---|
| Only Cloudflare can reach the origin (Authenticated Origin Pulls) | `nginx/snippets/authenticated-origin-pulls.conf` | Live check in `docs/RUNBOOK.md` | ◐ |
| HTTPS everywhere, HSTS, and the security headers on every response | `nginx/snippets/security-headers.conf` | `scripts/probe_headers.sh` in CI (`headers` job) and in `scripts/smoke.sh` | ✅ |
| Cloudflare features that inject scripts (Web Analytics) stay off | Cloudflare dashboard; `docs/RUNBOOK.md` | `scripts/smoke.sh` step 5 | ◐ |
| A Content Security Policy that blocks any script the site didn't ship | — | — | ⏳ lands with P2-A4 |
| Push payloads are end-to-end encrypted to the contact's browser (Web Push encryption) | `pywebpush` in `core/notifications.py` | Library behaviour | ◐ |

**What remains (✗):** Cloudflare decrypts every request, so it sees passwords at login, usernames, contact emails, and which pages each IP opens. A compromised CDN or host could serve altered JavaScript that captures the PIN. That is the limit of any encryption delivered by a web page; a CSP narrows it (an injected third-party script is blocked) but cannot remove it, because the same party could change the CSP. Brevo sees each alert email (contact address, survivor's username, time). These are stated on `/privacy.html` under "Who else handles data".

### A7 · Anyone on the internet

| Mitigation | Implemented in | Proven by | Status |
|---|---|---|---|
| Sign-ups are invite-only until legal and advocacy review (H6, D1) | `services/auth.py` `check_signup_allowed`; `BETA_SIGNUPS_ENABLED=false` | `backend/tests/test_signup_gate.py` | ✅ |
| Rate limits on every public write endpoint | `core/rate_limit.py`, `api/*.py` | `backend/tests/test_rate_limit.py` | ✅ |
| Notes and contact names are rendered with `textContent`, never as HTML | `html/log.html`, `html/checkin.js` | Review | ◐ |
| State-changing routes take JSON with no CORS middleware, so a cross-site form can't reach them (why `SameSite=Lax` is safe); the contact form now refuses form-encoded posts | `backend/app/main.py` (no CORS), `api/*.py` | `test_contact.py::test_form_encoded_posts_are_refused`, `test_sessions.py` | ✅ lane/a (P2-A17, P2-C5) |
| Clickjacking: `X-Frame-Options: SAMEORIGIN` | `security-headers.conf` | `scripts/probe_headers.sh` | ✅ (`frame-ancestors 'none'` **lands with P2-A4**) |
| Two alert loops can't double-alert (M1): the pass runs under a Postgres advisory lock; the loop is off by default outside production | `services/checkin.py` `ALERT_PASS_LOCK_KEY`, `core/config.py` | `test_alert_pass.py` | ✅ lane/a (P2-A8) |
| Repeated 429s from one address email the operator once (threshold 50/hour, at most 5 emails a day); the address is never stored or emailed | `core/abuse_alert.py`, `core/middleware.py` | `test_abuse_alert.py` | ✅ lane/a (P2-F3) |
| Uptime and alert-loop heartbeat page a person: `HEALTHCHECK_PING_URL` is requested only after a pass that held the lock and finished | `core/notifications.py` `ping_healthcheck`; setup in `docs/RUNBOOK.md` "Monitoring" | `test_healthcheck_ping.py`; the forced test in the runbook (not yet run) | ◐ code ✅ lane/a (P2-F2); accounts not set up yet |

**What remains (✗):** the rate limiter and login throttle live in one process's memory, so they reset on restart and wouldn't hold with a second worker (accepted for Phase 2, `docs/PHASE2_PLAN.md` §5). A logged-in user can make the server send invite emails to any address; with sign-ups invite-only this is bounded, but it spends the same 300-a-day Brevo quota that alerts depend on. *Recommendation (new ticket):* a per-account daily cap on invites.

---

## 4. Worked examples: the six High findings

Each one shows the actor, how the hole worked, and what now proves it is closed. Source: `docs/REVIEW_ENGINEERING.md`.

**H1 · Rate limits keyed on Cloudflare's IP (A2, A7).** Behind Cloudflare, `$remote_addr` was an edge IP shared by many visitors: one attacker could exhaust the login limit for everyone on that edge while never being limited personally. *Fix:* nginx restores the visitor IP from `CF-Connecting-IP`, trusted only from Cloudflare's published ranges (`nginx/snippets/cloudflare-realip.conf`, refreshed by `scripts/update_cf_ranges.sh`); the app trusts `X-Real-IP` only with `TRUST_PROXY_HEADERS=true`. *Proof:* `test_spoofed_real_ip_is_ignored_without_trusted_proxy`, `test_visitors_behind_the_proxy_get_separate_buckets`. *Residual:* in-memory, single worker.

**H2 · Private pages served without security headers (A1, A7).** An `add_header` inside the private-pages `location` silently discarded every inherited header, so `/log.html` could be framed and indexed. *Fix:* one snippet, `nginx/snippets/security-headers.conf`, included at server level and in every location that sets its own header. *Proof:* `scripts/probe_headers.sh` in the CI `headers` job against a real nginx, and as step 1 of `scripts/smoke.sh` after every deploy.

**H3 · A wrong PIN could fork the vault (A1, and the survivor's own mistake).** On an empty vault any PIN was accepted, so notes could be written under a mistyped PIN and become unreadable under the real one. *Fix:* a key-check blob (a constant encrypted under the PIN) stored at setup and write-once (migration `0003`, `services/evidence.py` `set_salt`/`set_key_check`); `log.html` only accepts a PIN that decrypts it. *Proof:* `test_pin_setup_stores_key_check_with_salt`, `test_key_check_backfill_is_write_once`, `test_key_check_is_per_user`; the key-check cases in `tests/web/crypto.test.mjs`; 16/16 in `tests/browser/notes_pin.mjs` (headless Chrome, run by hand).

**H4 · A contact's push device could be silently reassigned (A4).** `endpoint` was globally unique, so becoming a contact for a second survivor moved the device away from the first, with no one told. *Fix:* uniqueness on `(trusted_contact_id, endpoint)` (migration `0004`); dead endpoints are pruned for every contact. *Proof:* the three push tests listed under A4. *Residual:* none known on `lane/a`, where the survivor now sees when a contact's push was lost (P2-E5); on `phase2` alone they aren't told.

**H5 · Lockout as a weapon (A2, A4).** Eight failures locked the account for everyone for 15 minutes, so anyone who knew the username could keep the survivor out indefinitely. *Fix:* `core/login_throttle.py` delays only the guessing (IP, username) pair; recovery always works. *Proof:* the four throttle tests under A2. *Residual:* the old `failed_login_count`/`locked_until` columns are kept unused for one release (drop in migration `0008`).

**H6 · Live sign-ups ahead of review (A7, and every future user).** *Fix:* invite-only (`BETA_SIGNUPS_ENABLED=false`, `BETA_INVITE_CODES`, constant-time compare). *Proof:* `backend/tests/test_signup_gate.py`. Re-opening is P2-B10, allowed only after the legal (P2-C3) and advocacy (P2-C4) reviews are resolved.

---

## 5. Decisions recorded here

### D7 · No CAPTCHA (deferred)
Hosted CAPTCHAs (Cloudflare Turnstile, hCaptcha, reCAPTCHA) are third-party scripts. Loading one would tell that third party which IP visited the sign-up or login page, break the promise of "no third-party scripts" on `/privacy.html`, and, on a monitored device, add a request to a recognisable domain. The abuse they prevent is already bounded: sign-ups need an invite code (H6), every public write is rate-limited per real IP (H1), and password guessing is throttled per pair (H5). **Revisit** only if abuse alerting (P2-F3) shows sustained automated traffic, and then prefer a self-hosted proof-of-work over a hosted service.

### D8 · No audit log of logins or access
**Decision (default, owner may revisit):** keep no history of login IPs, user agents, or page access, per user or otherwise. Only `users.last_login_at` and each session's `created_at` / `last_seen_at` exist, because sessions need them.

*Why:* for this audience the audit log *is* the risk. A table of "this account logged in from this IP at these times" is a location history of a survivor. It would be the most valuable thing in a breach (A3), the first thing named in a subpoena (A5), and something an abuser with legal leverage (custody discovery) could demand. Its benefit, spotting a compromised account, is better delivered to the survivor directly, without retention: see the "where you're signed in" recommendation under A2. Operators get the signal they need from in-memory counters (P2-F3) rather than stored records.

*What this costs:* after a breach we can't say which accounts were accessed from where. `docs/INCIDENT_PLAN.md` assumes the worst instead.

### MFA · Deferred out of Phase 2
Every second factor available to a web app conflicts with the shared-device threat model (A1):
- **SMS or email codes** go to a phone plan or inbox the abuser may share or monitor, and need us to collect a phone number or email we deliberately don't.
- **An authenticator app** (TOTP) is an icon on the shared phone that says "this person has a secret account".
- **Passkeys** are unlocked by the device's own screen lock, which the abuser may know, and synced passkeys sit in an Apple or Google account the abuser may control.

The real attacks in A2 come from someone who already has the device or the password, and a second factor on the same device doesn't stop them. Recovery codes already act as the second factor for recovery. **Revisit** with the advocacy reviewer (P2-C4); a passkey offered as an *option* is the most likely candidate.

---

## 6. Gaps found while writing this (proposed new tickets)

These are not in `docs/PHASE2_PLAN.md` yet.

1. ~~**The alert loop can stop for good, silently.**~~ On `phase2`, `run_alert_loop()` has no `try` around a pass, so one failed query ends the background task while `/api/health` keeps answering. **Fixed on `lane/a`** (`test_alert_pass.py::test_loop_keeps_running_after_a_failed_pass`), and the heartbeat (P2-F2) would notice if it recurred.
2. **"Where you're signed in"** for the survivor (count and last-seen, no IPs), plus a short undo for deleted notes (A2).
3. **A daily cap on invite emails per account**, so the Brevo quota that alerts depend on can't be spent by one account (A7).
4. **A test that the raw session token never reaches the database** (A3), and tests for the contact's "stop" and the survivor's contact removal (A4).
5. **Say plainly on `checkin.html` that a trusted contact is a person, not a service**: they may miss or ignore an alert, and the check-in is not a substitute for calling 911 (A4; "no false promises", `docs/DESIGN2.md` §2).
