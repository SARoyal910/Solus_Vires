# Solus Vires Architecture

## Current Phase

**Last updated:** 2026-10-02 on branch `lane/c` (Phase 2 ops, docs, PWA), based on `phase2` at `83be254`; live is still `main` at `83d1f08`. Status lives in `docs/PROGRESS.md`; Phase 2 work is tracked in `docs/PHASE2_PLAN.md`.

Phase 1 (prototype) built public resource pages, accounts, a private client-side-encrypted notes log, and trusted-contact "I'm OK" check-ins. Phase 2 is turning that into something an advocate could recommend: Sprints 0–1 (safety fixes, tests, CI, backups) and the first content and trust pages are live.

## Deployment

- **Production:** a DigitalOcean droplet running `docker-compose.yml` (nginx `web`, FastAPI `api`, Postgres `db`) from a checkout of `main`, updated by hand with `git pull` and `scripts/deploy.sh` (steps in `docs/RUNBOOK.md`). The api runs the code built into its image; there is no source bind mount in production (the live-reload mount lives in a gitignored `docker-compose.override.yml`, from `docker-compose.override.example.yml`).
- **Migrations** are an explicit deploy step, `scripts/migrate.sh` (`alembic upgrade head` in a one-off container), never run on container start. The api's healthcheck compares the database's revision with the image's, so a deploy that skips the step shows `unhealthy` and fails `docker compose up --wait`. Static pages don't wait for the api.
- **After every deploy:** `scripts/smoke.sh https://solusvires.com` (headers, `/api/health`, every page 200, private pages `no-store`, no third-party scripts).
- **Monitoring and who gets paged:** UptimeRobot on `/api/health` and a Healthchecks.io heartbeat after each alert pass (`HEALTHCHECK_PING_URL`) email the owner, Steven Royal (setup in `docs/RUNBOOK.md`, not yet done). What to do when something breaks: `docs/INCIDENT_PLAN.md`.
- **Certificates:** Cloudflare terminates public TLS; the origin uses a Cloudflare Origin CA certificate (valid to 2040) in `certs/`.
- **Cloudflare** proxies the public hostname. nginx trusts `CF-Connecting-IP` only from Cloudflare's published ranges (`nginx/snippets/cloudflare-realip.conf`) and refuses connections without Cloudflare's origin-pull client certificate (`authenticated-origin-pulls.conf`). Cloudflare Web Analytics must stay disabled.
- **Logging:** nginx `access_log off` and uvicorn `--no-access-log`, so no record of which visitor opened which page; Docker logs are size-capped. The privacy page promises this.
- **Backups:** nightly `pg_dump` on the droplet, encrypted to an `age` public key (`scripts/backup.sh`); restore rehearsed with `scripts/restore_check.sh`.
- **The owner's Mac** runs a local copy of the stack for development; it is not the origin. (The dead static-hosting config, `wrangler.jsonc` and `html/_redirects`, was deleted in P2-B8; nginx is the only thing that serves the site.)
- **Testing:** `scripts/test.sh` (ruff + pytest on Python 3.12 against a throwaway Postgres), `node --test tests/web/`, `scripts/preview.sh` (local preview at 127.0.0.1:8099), headless-Chrome checks in `tests/browser/` (run against the preview), and CI in `.github/workflows/ci.yml` (backend, web crypto, a full-stack deploy with header probe and smoke test, shellcheck, and the offline-copy browser test). Dependabot (`.github/dependabot.yml`) proposes pip, base-image, and Actions updates weekly.

## Backend

- FastAPI app factory in `backend/app/main.py` — also owns the background check-in alert loop (an `asyncio` task started in the app's `lifespan`, no extra scheduler dependency)
- API routers in `backend/app/api` (`health`, `contact`, `auth`, `evidence`, `checkin`)
- Runtime configuration in `backend/app/core/config.py`
- Security headers in `backend/app/core/middleware.py`
- Database engine/session in `backend/app/core/db.py`; password hashing and opaque session tokens in `backend/app/core/security.py`
- Per-IP rate limiting in `backend/app/core/rate_limit.py` (trusts `X-Real-IP` only when `TRUST_PROXY_HEADERS=true`) and per-(IP, username) login slowdown in `backend/app/core/login_throttle.py`; both in-process, single-worker only
- Invite-only registration gate (`BETA_SIGNUPS_ENABLED`, `BETA_INVITE_CODES`) in `backend/app/services/auth.py`
- Web Push (VAPID) and Brevo transactional email send helpers in `backend/app/core/notifications.py` — both no-op with a log line, not an error, when unconfigured
- SQLAlchemy models in `backend/app/models/` (`auth.py`: `User`, `Session`, `RecoveryCode`; `evidence.py`: `CaseProfile`, `EvidenceEntry`; `checkin.py`: `TrustedContact`, `PushSubscription`, `CheckinSchedule`)
- Alembic migrations in `backend/migrations/`
- Contact business logic in `backend/app/services/contact.py`; auth/evidence logic in `backend/app/services/auth.py` and `evidence.py`; check-in logic (including the HMAC-signed invite-token scheme — see `docs/CHECKIN.md`) in `backend/app/services/checkin.py`

The contact service deliberately does not log survivor-provided message content. The evidence service goes further: it never receives plaintext at all — `CaseProfile`/`EvidenceEntry` rows store only client-encrypted ciphertext, so the server has no way to read, log, or hand over evidence content even if compelled to. Production intake for the plain contact form should still move to encrypted storage or a secure partner inbox with retention limits and audit logging.

Authentication uses opaque, DB-backed session tokens (not JWT) in an `httponly`/`SameSite=Strict` cookie (moving to `Lax` is P2-A17), so sessions can be instantly and fully revoked (`/api/auth/logout-all`) — deliberately chosen over JWT for that revocation guarantee, since a survivor may need to invalidate access the moment a shared device is compromised.

## Frontend

Static public pages live in `html/`:

- `index.html` — leads with three paths: in danger now, not sure what's happening, want to plan
- `is-this-abuse.html` + `is-this-abuse.js` — forms of abuse and a private self-check (stores and sends nothing)
- `for-men.html`, `help-someone.html`, `if-you-get-an-alert.html` — support for male survivors, friends and family, and trusted contacts
- `about.html`, `privacy.html` — who runs the site; exactly what's stored (keep in sync with the code, see the comment at its bottom)
- `local-help.js` — the "find help in your state" picker on Legal and Resources
- `es/` — Spanish crisis path (home, emergencia, es-abuso, seguridad, recursos); draft pending native-speaker review
- `resources.html` — categorized directory of verified, currently-operating national hotlines and support orgs (crisis/DV, tech safety, population-specific, financial abuse)
- `safety.html` — in-depth safety planning: living with them, getting ready, documents, phones, children, pets, after leaving, specific situations
- `legal.html` — protective orders, reporting to police, housing, custody, immigration, plus verified free legal aid
- `recovery.html` — trauma-informed recovery framework (Herman's three-stage model), interactive grounding tools (box breathing, 5-4-3-2-1), and a verified free/low-cost mental-health resource directory
- `recovery.js` — client-only interactive logic for the recovery tools; progress is tracked in `localStorage` only, never sent to the server
- `partners.html` — roadmap page; linked from Resources, not the main nav
- `emergency.html` — 911/text-911 plus non-dispatch crisis lines (988, Crisis Text Line, National DV Hotline)
- `contact.html` — where to get help now; the old form is gone until a monitored inbox exists (P2-C5)
- `account.html` — registration, login, recovery-code display, logout
- `log.html` — PIN-locked, client-side-encrypted notes and case-profile editor, reached from `account.html` (nav label "Notes & Check-ins"); a key-check blob rejects a wrong PIN even on an empty vault
- `evidence-crypto.js` — dependency-free WebCrypto helpers (PBKDF2 key derivation + AES-GCM) used only by `log.html`
- `checkin.html` — survivor-facing check-in schedule + trusted-contact management, linked from `account.html` and `emergency.html`, not from the main nav (same discoverability pattern as `log.html`)
- `checkin-invite.html` — the public, token-authenticated page a trusted contact uses to accept/decline an invite and opt in to Web Push
- `sw.js` — the service worker: Web Push for trusted contacts, and the opt-in offline copy of the crisis pages (below). Registered only from `checkin-invite.js` or `offline.js`, never on page load
- `manifest.json`, `icon-*.png` (`icon.svg` is the source) — make the site installable; `offline.js` — the "Save on this device" panel on Emergency and Resources (English and Spanish)
- `checkin.js`, `checkin-invite.js` — plain JS for the two pages above; see `docs/CHECKIN.md`

### Installable app and offline copy (P2-E9)

The site can be added to a home screen, and the Emergency and Resources pages (English and Spanish) can be kept for use without a signal. Choices, made for the shared-device threat model (`docs/THREAT_MODEL.md`, A1):

- **Opt-in, visible, removable.** Nothing is stored and no service worker is registered until someone presses "Save on this device" on one of those pages; the same panel removes it (and unregisters the worker unless it also carries a trusted contact's push alerts). A saved copy is one more trace of the site on a device, and survives "clear history" unless site data is cleared too, so it can't be on by default. `/privacy.html` says so.
- **No install prompt.** The site never asks to be installed, and `shared.js` suppresses Chrome's automatic "Add to Home screen" banner, which would otherwise pop up on its own on a shared phone. Installing stays available from the browser menu for anyone who wants it.
- **Name and icon.** The installed name is "Solus Vires", the same as the tab title, not a disguise (a fake "Weather" app is out of scope in `docs/DESIGN2.md` §5 and would confuse people). The name doesn't mention abuse, and the icon is a plain grey "SV" on dark slate, not the bright shield logo, so a home-screen icon is unremarkable. iOS lets the person rename it when adding it.
- **Never stale while online.** Network first: listed pages are always revalidated with the server and the saved copy refreshed from the answer, so the copy is used only when the network fails; when the device reports it's offline, the page says it's a saved copy and when it was saved. Only the listed public files are ever written to the cache; private pages and `/api/` never are. Offline, any page falls back to the saved Emergency page.
- **Tested** by `tests/browser/offline.mjs`.

External links in `resources.html`, `legal.html`, `recovery.html`, and `emergency.html` were verified organization-by-organization (official `.org`/`.gov` domains, current phone/text numbers) rather than reconstructed from memory. A couple of deliberate caveats are called out in the copy itself: Open Path Collective is low-cost, not free; NAMI's HelpLine and the Eldercare Locator are not 24/7 crisis lines.

These pages are served by FastAPI during local development and by nginx in the Docker stack.

## Production Requirements Before Sensitive Features

Status against this list as of the accounts + notes MVP:

- Complete a survivor safety threat model. **Done** — `docs/THREAT_MODEL.md` (P2-C6): seven actors, each mitigation mapped to code and tests, open items marked by ticket.
- Add proper authentication and role-based access control. **Partially done** — username/password auth with opaque sessions and lockout exists; there is a single user role, no RBAC, no MFA.
- Encrypt sensitive fields at rest. **Done for evidence/case-profile content** (client-side, zero-knowledge — the server never holds a usable key). Not applicable yet to the plain contact-form intake, which still needs its own encrypted storage before production use.
- Add audit logging that avoids storing unsafe content. **Decided against by default** — access logs are off and no login history is kept; the reasoning is in `docs/THREAT_MODEL.md` §5 (D8).
- Add database migrations and backup/restore testing. **Done** — Alembic migrations (0001–0004); encrypted nightly backups on the droplet, and a production backup restored successfully on 2026-09-26.
- Add rate limiting, abuse detection, and alerting. **Mostly done** — per-IP rate limits on public endpoints, per-(IP, username) login slowdown, invite-only sign-ups. Abuse alerting is P2-F3; hosted CAPTCHA deliberately deferred (D7).
- Define retention and deletion policies. **Partially done** — evidence entries/case profile/trusted contacts can each be deleted individually, and `POST /api/auth/delete-account` (password-confirmed) now permanently deletes the account and everything tied to it in one step, relying on `ondelete="CASCADE"` across every child table. Still not done: a defined *retention window* for data the user hasn't manually deleted (i.e., how long is it kept by default, not just "can it be deleted").
- Verify partner organizations before access. Not applicable yet — no partner-facing access exists.
- Get legal review for privacy, mandatory reporting, and emergency claims. **Not done** — this remains a hard prerequisite before real-world use with actual survivors.
- Validate emergency features with public-safety and advocacy partners. Not applicable yet — no emergency features exist.

Also intentionally not built (see `docs/TODO.md` for the reasons): real-time location sharing (a separate, larger feature than the check-in system above — deliberately not bundled in), any public-facing registry of alleged abusers (rejected as a defamation/retaliation-safety risk — see README), file/photo evidence upload, and a disguised/skinned UI beyond generic page labeling.

## Location and Emergency Features

Location tracking must be explicit, visible, revocable, temporary, and survivor-controlled. It must never run as hidden monitoring. Emergency-response language must not imply 911 dispatch unless the system has a real, tested integration or staffed response partnership.
