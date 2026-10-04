# Progress

The one status page: what exists and is live right now. Detail lives in each feature's own doc; Phase 2 work in progress is tracked ticket by ticket in `docs/PHASE2_PLAN.md`.

**Last verified against production:** 2026-10-04, `main` at `2b81477` on the droplet (smoke test green from the droplet and from the Mac; CSP, `/plain/`, manifest and `/api/health` confirmed live).

## Live on solusvires.com

**Phase 1 (prototype) — foundation**
- Static public pages (`html/`), FastAPI backend, nginx + Docker Compose on a DigitalOcean droplet behind Cloudflare (`docs/RUNBOOK.md`)
- Username/password accounts, opaque DB-backed sessions, recovery codes (`docs/ACCOUNTS_AND_NOTES.md`)
- `/log.html` private notes: PIN-locked, AES-GCM encrypted in the browser; the server stores only ciphertext
- Trusted-contact "I'm OK" check-ins with Web Push + email alerts (`docs/CHECKIN.md`)
- Recovery & Wellness tools (`/recovery.html`), full account deletion

**Phase 2 — Sprint 0–1: safety fixes and foundations (deployed 2026-09-26)**
- Security headers on every page, including the private ones that had none; HSTS
- Rate limiting keyed on the real visitor IP via Cloudflare's `CF-Connecting-IP`
- A wrong Notes PIN can no longer split the vault (key-check); PIN minimum 12 characters
- Failed logins slow only the guessing (IP, username) pair; nobody can lock a survivor out
- One phone can be the trusted contact for several survivors without silently losing alerts
- New accounts are invite-only (`BETA_INVITE_CODES`) until legal and advocacy review
- nginx answers only Cloudflare (Authenticated Origin Pulls, Global)
- Encrypted nightly backups on the droplet; one restored successfully
- Test suite (47 backend + 6 browser-crypto tests), CI on every push, header probe (`scripts/probe_headers.sh`)

**Phase 2 — content and trust (deployed 2026-09-26)**
- Homepage leads with "in danger now / not sure what's happening / want to plan" and says plainly it's for every gender
- New pages: Is this abuse? (with a private self-check), Support for men, How to help someone, If you get an alert
- Safety Planning and Legal pages rewritten in depth; a state picker linking to each state's WomensLaw page
- Spanish crisis path at `/es/` (draft, pending native-speaker review)
- About (run by Steven Royal, through Omnia Royal LLC) and a Privacy statement written from a code audit
- No access logs in nginx or the API; Docker logs size-capped; Cloudflare Web Analytics disabled (it had been injecting a tracker)
- Every hotline, number, and organization checked against its own website; sources at the bottom of each page

**Phase 2 — Sprints 2–6 code (deployed 2026-10-04, `main` at `2b81477`)**

Merged and tested 2026-10-02, deployed by the owner 2026-10-04 following `docs/RUNBOOK.md` "Next deploy" (new `RECOVERY_CODE_PEPPER`, database password rotated, migrations 0005–0007 applied, no source bind mount, smoke green).

**Phones**
- The header is one row on phones (brand, menu button, Quick Exit); the page links open from the menu button

**Safety and hardening (Sprint 2)**
- A Content-Security-Policy on every page: no inline script or style, nothing from other sites
- Two alert loops can't double-alert; one failed pass no longer stops the loop for good
- Unknown usernames take as long to reject as wrong passwords
- Recovery codes stored as a keyed hash; session cookie `SameSite=Lax`; expired sessions swept
- The API refuses to start in production with an empty or default secret
- Migrations are an explicit deploy step (`scripts/migrate.sh`); a deploy that skips it fails loudly. `scripts/deploy.sh` and `scripts/smoke.sh`

**Notes**
- PIN strength hint and clearer warnings; "Unlocking…" state
- Print or save a copy of your notes (made in the browser, no network); search
- A fillable, encrypted safety plan
- Encrypted photos and screenshots, with location and other hidden details removed first

**Check-ins**
- Contacts are told when the alerts have stopped; alerts are numbered and say how often they repeat
- The survivor sees an alert history and whether each contact's notifications still work; a contact who stopped can be invited again
- Changing the schedule moves the deadline

**Everyone**
- Quick Exit opens a neutral site in a new tab and replaces the page; "Esc twice" hint
- Plain view: an opt-in, low-key look, also available without JavaScript under `/plain/`
- Neutral tab titles on private pages
- "Save on this device": Emergency and Resources (English and Spanish) open without internet, only if asked for
- Contact form that emails a monitored inbox (off until an address is set)
- Older adults section on Safety; terms section on Privacy
- Pages revalidate on every visit, so nobody sees a stale copy

**Operations and docs**
- Threat model (`docs/THREAT_MODEL.md`), incident plan (`docs/INCIDENT_PLAN.md`), monitoring steps, Dependabot
- Operator email on repeated rate-limit hits; optional heartbeat ping after each alert pass
- Review request packets drafted for legal counsel and an advocacy organization (not sent)

**Tests on `main`:** 127 backend, 21 browser-side unit tests, and five headless-Chrome suites (Notes PIN 29, vault 28, site UI 41, offline copy 21, and a click-through of every page under the real policy with zero violations). All five CI jobs are green on GitHub.

## Verified vs. not yet verified

Verified: the full check-in round trip against a real stack (`docs/CHECKIN.md`); Notes PIN flows in real Chrome (`tests/browser/notes_pin.mjs`, 16/16); a production backup decrypted and restored; the live site's headers, sign-up gate, and origin lock.

Not yet verified in the real world:
- A push notification delivered to a real phone, and the iOS "Add to Home Screen" flow
- A real email delivered via Brevo
- The alert loop firing on its own timer (only triggered manually)
- That access logging is off on the droplet (owner to check `docker logs solusvires_web`)

## Not done yet

Everything left needs the owner or someone outside the project; the list is `docs/TODO.md`. In short: deploy `phase2`, send the legal and advocacy review requests and work through the answers (P2-C3, C4, C7), a native-speaker review of `/es/` (P2-D8), a contact address, real-device checks (P2-E6), monitoring accounts (P2-F2), the retention policy after counsel (P2-F6), and reopening sign-ups only after both reviews (P2-B10). A PIN-change flow for Notes is not built.
