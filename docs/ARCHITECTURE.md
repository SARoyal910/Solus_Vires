# Solus Vires Architecture

## Current Phase

The current codebase is a Phase 1 public resource foundation. It is intended to serve public pages, basic contact intake, and partner-facing product direction.

## Backend

- FastAPI app factory in `backend/app/main.py`
- API routers in `backend/app/api`
- Runtime configuration in `backend/app/core/config.py`
- Security headers in `backend/app/core/middleware.py`
- Contact business logic in `backend/app/services/contact.py`

The contact service deliberately does not log survivor-provided message content. Production intake should use encrypted storage or a secure partner inbox with retention limits and audit logging.

## Frontend

Static public pages live in `html/`:

- `index.html`
- `resources.html`
- `safety.html`
- `legal.html`
- `partners.html`
- `emergency.html`
- `contact.html`

These pages are served by FastAPI during local development and by nginx in the Docker stack.

## Production Requirements Before Sensitive Features

Before adding survivor accounts, referrals, real-time location, or emergency workflows:

- Complete a survivor safety threat model.
- Add proper authentication and role-based access control.
- Encrypt sensitive fields at rest.
- Add audit logging that avoids storing unsafe content.
- Add database migrations and backup/restore testing.
- Add rate limiting, abuse detection, and alerting.
- Define retention and deletion policies.
- Verify partner organizations before access.
- Get legal review for privacy, mandatory reporting, and emergency claims.
- Validate emergency features with public-safety and advocacy partners.

## Location and Emergency Features

Location tracking must be explicit, visible, revocable, temporary, and survivor-controlled. It must never run as hidden monitoring. Emergency-response language must not imply 911 dispatch unless the system has a real, tested integration or staffed response partnership.
