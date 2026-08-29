# Solus Vires Architecture

## Current Phase

The current codebase is a Phase 1 public resource foundation, plus an early Phase 2 slice: accounts and a private, client-side-encrypted notes/evidence log. It is intended to serve public pages, basic contact intake, partner-facing product direction, and (new) a minimal survivor account system.

## Backend

- FastAPI app factory in `backend/app/main.py`
- API routers in `backend/app/api` (`health`, `contact`, `auth`, `evidence`)
- Runtime configuration in `backend/app/core/config.py`
- Security headers in `backend/app/core/middleware.py`
- Database engine/session in `backend/app/core/db.py`; password hashing, opaque session tokens, and lockout logic in `backend/app/core/security.py`
- SQLAlchemy models in `backend/app/models/` (`auth.py`: `User`, `Session`, `RecoveryCode`; `evidence.py`: `CaseProfile`, `EvidenceEntry`)
- Alembic migrations in `backend/migrations/`
- Contact business logic in `backend/app/services/contact.py`; auth/evidence logic in `backend/app/services/auth.py` and `evidence.py`

The contact service deliberately does not log survivor-provided message content. The evidence service goes further: it never receives plaintext at all — `CaseProfile`/`EvidenceEntry` rows store only client-encrypted ciphertext, so the server has no way to read, log, or hand over evidence content even if compelled to. Production intake for the plain contact form should still move to encrypted storage or a secure partner inbox with retention limits and audit logging.

Authentication uses opaque, DB-backed session tokens (not JWT) in an `httponly`/`SameSite=Strict` cookie, so sessions can be instantly and fully revoked (`/api/auth/logout-all`) — deliberately chosen over JWT for that revocation guarantee, since a survivor may need to invalidate access the moment a shared device is compromised.

## Frontend

Static public pages live in `html/`:

- `index.html`
- `resources.html`
- `safety.html`
- `legal.html`
- `partners.html`
- `emergency.html`
- `contact.html`
- `account.html` — registration, login, recovery-code display, logout
- `log.html` — labeled "Notes" in navigation (deliberately generic); PIN-locked, client-side-encrypted notes and case-profile editor
- `evidence-crypto.js` — dependency-free WebCrypto helpers (PBKDF2 key derivation + AES-GCM) used only by `log.html`

These pages are served by FastAPI during local development and by nginx in the Docker stack.

## Production Requirements Before Sensitive Features

Status against this list as of the accounts + notes MVP:

- Complete a survivor safety threat model. **Not done** — this MVP was built with DV-tech safety practices in mind (no email/SMS recovery, zero-knowledge evidence encryption, instant full session revocation, generic labeling) but has not had a formal threat-modeling pass.
- Add proper authentication and role-based access control. **Partially done** — username/password auth with opaque sessions and lockout exists; there is a single user role, no RBAC, no MFA.
- Encrypt sensitive fields at rest. **Done for evidence/case-profile content** (client-side, zero-knowledge — the server never holds a usable key). Not applicable yet to the plain contact-form intake, which still needs its own encrypted storage before production use.
- Add audit logging that avoids storing unsafe content. **Not done** — deliberately deferred; with zero-knowledge content there's little to log beyond what DB rows already imply, and logging things like login IPs is itself a risk to design carefully, not add by default.
- Add database migrations and backup/restore testing. **Migrations done** (Alembic, `backend/migrations/`). Backup/restore testing **not done**.
- Add rate limiting, abuse detection, and alerting. **Partially done** — basic login lockout/backoff exists; no rate limiting, CAPTCHA, or abuse alerting.
- Define retention and deletion policies. **Not done** — evidence entries/case profile can be deleted by the user, but there's no defined retention policy or account-deletion flow yet.
- Verify partner organizations before access. Not applicable yet — no partner-facing access exists.
- Get legal review for privacy, mandatory reporting, and emergency claims. **Not done** — this remains a hard prerequisite before real-world use with actual survivors.
- Validate emergency features with public-safety and advocacy partners. Not applicable yet — no emergency features exist.

Also intentionally not built: a trusted-contact "I'm OK" check-in/alert system (planned as the next phase), any public-facing registry of alleged abusers (rejected as a defamation/retaliation-safety risk — see README), file/photo evidence upload, and a disguised/skinned UI beyond generic page labeling.

## Location and Emergency Features

Location tracking must be explicit, visible, revocable, temporary, and survivor-controlled. It must never run as hidden monitoring. Emergency-response language must not imply 911 dispatch unless the system has a real, tested integration or staffed response partnership.
