# Solus Vires

Solus Vires is a public safety and resource platform for domestic abuse survivors, families, and advocacy partners.

This repository currently contains a Phase 1 foundation, plus an early Phase 2 feature:

- Static public resource pages
- FastAPI backend with health and contact endpoints
- Accounts (`/account.html`) and a private, end-to-end encrypted notes/evidence log (`/log.html`) — see "Accounts and private notes" below
- Nginx reverse proxy configuration
- Docker Compose development/deployment skeleton
- Safety-minded copy that avoids false emergency dispatch claims

## Local Development

```bash
cd /Users/saroyal/Projects/solusvires
source .venv/bin/activate
python -m uvicorn backend.app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/
```

Useful routes:

```text
GET  /api/health
POST /api/contact
GET  /docs
```

## Docker

Create a local env file from the example before running Docker:

```bash
cp .env.example .env
```

Set a strong `POSTGRES_PASSWORD`, then run:

```bash
docker compose up --build
```

## Accounts and private notes

`/account.html` lets someone create a username/password account (no email or phone number required, to avoid recovery flows that could be seen by an abusive person sharing that inbox or phone plan). `/log.html` ("Notes" in the nav, deliberately unlabeled as anything more specific) is a private, per-account notes/evidence log and case-profile page. Content is encrypted client-side in the browser with a separate Notes PIN before it is ever sent to the server — the server and database only ever store ciphertext, never plaintext, and there is no public or cross-account visibility of any of it (there is no "abuser registry" and none is planned; see below).

Real limitations to know before relying on this:
- The Notes PIN has **no recovery path** — if it's forgotten, that content is permanently unreadable, including to the site operator. This is intentional (zero-knowledge design), not a bug.
- There is no file/photo upload yet — text only, partly because photo EXIF metadata can itself leak identifying details like GPS location.
- This has not had a legal review, a security audit, or input from a domestic-violence advocacy organization. Treat it as a technical prototype, not a vetted safety tool, until that review happens.
- A public, crowdsourced "registry of abusers" was deliberately **not** built — it would be a serious defamation and retaliation-safety risk. Only a survivor's own private, non-public case notes exist.

## Safety Boundaries

This app is not yet an emergency dispatch system. Real-time location sharing, emergency response, partner referral workflows, a trusted-contact check-in/alert system, multi-factor authentication, and any public-facing registry require additional privacy, legal, mobile, reliability, and advocacy-partner design before launch — several of these are intentionally not built yet.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the build roadmap.
