# Solus Vires Architecture

## Current Phase

The current codebase is a Phase 1 public resource foundation, plus Phase 2: accounts, a private client-side-encrypted notes/evidence log, and a trusted-contact "I'm OK" check-in/alert system. It is intended to serve public pages, basic contact intake, partner-facing product direction, and a minimal survivor account system.

## Backend

- FastAPI app factory in `backend/app/main.py` — also owns the background check-in alert loop (an `asyncio` task started in the app's `lifespan`, no extra scheduler dependency)
- API routers in `backend/app/api` (`health`, `contact`, `auth`, `evidence`, `checkin`)
- Runtime configuration in `backend/app/core/config.py`
- Security headers in `backend/app/core/middleware.py`
- Database engine/session in `backend/app/core/db.py`; password hashing, opaque session tokens, and lockout logic in `backend/app/core/security.py`
- Web Push (VAPID) and Brevo transactional email send helpers in `backend/app/core/notifications.py` — both no-op with a log line, not an error, when unconfigured
- SQLAlchemy models in `backend/app/models/` (`auth.py`: `User`, `Session`, `RecoveryCode`; `evidence.py`: `CaseProfile`, `EvidenceEntry`; `checkin.py`: `TrustedContact`, `PushSubscription`, `CheckinSchedule`)
- Alembic migrations in `backend/migrations/`
- Contact business logic in `backend/app/services/contact.py`; auth/evidence logic in `backend/app/services/auth.py` and `evidence.py`; check-in logic (including the HMAC-signed invite-token scheme — see `docs/CHECKIN.md`) in `backend/app/services/checkin.py`

The contact service deliberately does not log survivor-provided message content. The evidence service goes further: it never receives plaintext at all — `CaseProfile`/`EvidenceEntry` rows store only client-encrypted ciphertext, so the server has no way to read, log, or hand over evidence content even if compelled to. Production intake for the plain contact form should still move to encrypted storage or a secure partner inbox with retention limits and audit logging.

Authentication uses opaque, DB-backed session tokens (not JWT) in an `httponly`/`SameSite=Strict` cookie, so sessions can be instantly and fully revoked (`/api/auth/logout-all`) — deliberately chosen over JWT for that revocation guarantee, since a survivor may need to invalidate access the moment a shared device is compromised.

## Frontend

Static public pages live in `html/`:

- `index.html`
- `resources.html` — categorized directory of verified, currently-operating national hotlines and support orgs (crisis/DV, tech safety, population-specific, financial abuse)
- `safety.html`
- `legal.html` — verified free legal-aid organizations plus educational topic summaries
- `recovery.html` — trauma-informed recovery framework (Herman's three-stage model), interactive grounding tools (box breathing, 5-4-3-2-1), and a verified free/low-cost mental-health resource directory
- `recovery.js` — client-only interactive logic for the recovery tools; progress is tracked in `localStorage` only, never sent to the server
- `partners.html`
- `emergency.html` — 911/text-911 plus non-dispatch crisis lines (988, Crisis Text Line, National DV Hotline)
- `contact.html`
- `account.html` — registration, login, recovery-code display, logout
- `log.html` — labeled "Notes" in navigation (deliberately generic); PIN-locked, client-side-encrypted notes and case-profile editor
- `evidence-crypto.js` — dependency-free WebCrypto helpers (PBKDF2 key derivation + AES-GCM) used only by `log.html`
- `checkin.html` — survivor-facing check-in schedule + trusted-contact management, linked from `account.html` and `emergency.html`, not from the main nav (same discoverability pattern as `log.html`)
- `checkin-invite.html` — the public, token-authenticated page a trusted contact uses to accept/decline an invite and opt in to Web Push
- `sw.js` — the Web Push service worker, registered only from the contact's browser
- `checkin.js`, `checkin-invite.js` — plain JS for the two pages above; see `docs/CHECKIN.md`

External links in `resources.html`, `legal.html`, `recovery.html`, and `emergency.html` were verified organization-by-organization (official `.org`/`.gov` domains, current phone/text numbers) rather than reconstructed from memory. A couple of deliberate caveats are called out in the copy itself: Open Path Collective is low-cost, not free; NAMI's HelpLine and the Eldercare Locator are not 24/7 crisis lines.

These pages are served by FastAPI during local development and by nginx in the Docker stack.

## Production Requirements Before Sensitive Features

Status against this list as of the accounts + notes MVP:

- Complete a survivor safety threat model. **Not done** — this MVP was built with DV-tech safety practices in mind (no email/SMS recovery, zero-knowledge evidence encryption, instant full session revocation, generic labeling) but has not had a formal threat-modeling pass.
- Add proper authentication and role-based access control. **Partially done** — username/password auth with opaque sessions and lockout exists; there is a single user role, no RBAC, no MFA.
- Encrypt sensitive fields at rest. **Done for evidence/case-profile content** (client-side, zero-knowledge — the server never holds a usable key). Not applicable yet to the plain contact-form intake, which still needs its own encrypted storage before production use.
- Add audit logging that avoids storing unsafe content. **Not done** — deliberately deferred; with zero-knowledge content there's little to log beyond what DB rows already imply, and logging things like login IPs is itself a risk to design carefully, not add by default.
- Add database migrations and backup/restore testing. **Migrations done** (Alembic, `backend/migrations/`). Backup/restore testing **not done**.
- Add rate limiting, abuse detection, and alerting. **Partially done** — basic login lockout/backoff exists; no rate limiting, CAPTCHA, or abuse alerting.
- Define retention and deletion policies. **Partially done** — evidence entries/case profile/trusted contacts can each be deleted individually, and `POST /api/auth/delete-account` (password-confirmed) now permanently deletes the account and everything tied to it in one step, relying on `ondelete="CASCADE"` across every child table. Still not done: a defined *retention window* for data the user hasn't manually deleted (i.e., how long is it kept by default, not just "can it be deleted").
- Verify partner organizations before access. Not applicable yet — no partner-facing access exists.
- Get legal review for privacy, mandatory reporting, and emergency claims. **Not done** — this remains a hard prerequisite before real-world use with actual survivors.
- Validate emergency features with public-safety and advocacy partners. Not applicable yet — no emergency features exist.

Also intentionally not built: real-time location sharing (a separate, larger feature than the check-in system above — deliberately not bundled in), any public-facing registry of alleged abusers (rejected as a defamation/retaliation-safety risk — see README), file/photo evidence upload, and a disguised/skinned UI beyond generic page labeling.

## Location and Emergency Features

Location tracking must be explicit, visible, revocable, temporary, and survivor-controlled. It must never run as hidden monitoring. Emergency-response language must not imply 911 dispatch unless the system has a real, tested integration or staffed response partnership.
