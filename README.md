# Solus Vires

Solus Vires is a free, private safety and resource site for anyone being hurt by a partner or family member, whatever their gender, and for the people around them. Live at https://solusvires.com (not yet promoted; accounts are invite-only until legal and advocacy review).

Where things stand: `docs/PROGRESS.md` (what's live), `docs/PHASE2_PLAN.md` (what's next), `docs/RUNBOOK.md` (deploy, backups, restore, monitoring), `docs/THREAT_MODEL.md` (who the site defends against, and how), `docs/INCIDENT_PLAN.md` (what to do when something goes wrong).
- `docs/SCALE.md`: how far the current setup scales, what fails first, and the staged plan for growing it
- `docs/PHASE3_PLAN.md`: what comes next, built around being the tool a survivor keeps alongside the hotline they call: public proof, the compromised-phone path, the trusted contact as a user, verifiable evidence, partner referrals
- `docs/DEPLOYPHASE2.md`: the owner's step-by-step list after the 2026-10-07 deploy (monitoring, Postmark, off-site backups, restore drill, canary, second person, review requests)
- `docs/INVESTOR_PACK.md`: the technical and operational evidence for a partner or investor conversation, with the blanks the owner fills from the dashboards

What's here:

- Public pages that lead with what someone needs: in danger now, not sure if it's abuse (`/is-this-abuse.html`), or wanting to plan (`/safety.html`); plus pages for men, for friends and family, and for trusted contacts who get an alert
- Verified directories of real hotlines, legal aid, and mental-health resources (`/resources.html`, `/legal.html`, `/recovery.html`), a find-help-in-your-state picker, and a Spanish crisis path (`/es/`)
- `/about.html` and `/privacy.html`: who runs the site and exactly what it stores
- `/watched-phone.html`: what the site protects and cannot on a shared or monitored device; `/for-advocates.html` and `/verify.html`: what a signed notes export proves, and an offline verifier for it
- A contact form (`/contact.html`) that emails the owner's inbox through Brevo and stores nothing, with a stated reply window and a plain "not for emergencies" line; it says it's off when no inbox is configured (`CONTACT_INBOX_EMAIL`)
- A Recovery &amp; Wellness page (`/recovery.html`) with a trauma-informed recovery framework and interactive grounding tools (box breathing, 5-4-3-2-1) — fully client-side, no backend or paid service required
- FastAPI backend (health, auth, encrypted notes, check-ins)
- Accounts (`/account.html`) and a private, end-to-end encrypted notes/evidence log (`/log.html`) — see "Accounts and private notes" below
- A trusted-contact "I'm OK" check-in system (`/checkin.html`) — see "Check-ins and trusted contacts" below
- Nginx reverse proxy configuration
- Docker Compose stack, deployed to a DigitalOcean droplet behind Cloudflare
- Safety-minded copy that avoids false emergency dispatch claims
- An installable app, with an opt-in offline copy of the Emergency and Resources pages (English and Spanish) for when there's no signal

## Local Development

```bash
scripts/preview.sh        # the site + API with a throwaway database at http://127.0.0.1:8099
scripts/preview.sh down   # stop it and discard the database
scripts/test.sh           # lint + backend tests (Python 3.12, throwaway Postgres)
node --test tests/web/    # browser encryption tests
node tests/browser/offline.mjs                    # offline copy + install, headless Chrome, against the preview
scripts/probe_headers.sh https://solusvires.com   # security headers on every page
scripts/smoke.sh https://solusvires.com           # headers + API + every page; read-only, the last step of every deploy
```

All of these run in Docker under their own compose projects, so they never touch another stack's containers or data. To run a second checkout's at the same time, give it its own names: `SV_TEST_PROJECT=sv-x scripts/test.sh`, `SV_PREVIEW_PROJECT=sv-x-preview PREVIEW_PORT=8130 scripts/preview.sh`.

Useful routes: `GET /api/health`, `GET /docs`.

## Docker

Create a local env file from the example before running Docker:

```bash
cp .env.example .env
```

Set a strong `POSTGRES_PASSWORD`, then run:

```bash
scripts/migrate.sh            # builds the api image and applies database migrations
docker compose up -d --wait   # starts nginx, the api and Postgres; fails if any isn't healthy
```

Migrations never run on container start: run `scripts/migrate.sh` after pulling a change that adds one. If you forget, the api shows `(unhealthy)` and `up --wait` says so. The image runs the code it was built with; for live reload while developing, `cp docker-compose.override.example.yml docker-compose.override.yml` (gitignored, so it never reaches production). On the droplet, deploy with `scripts/deploy.sh https://solusvires.com` (`docs/RUNBOOK.md`).

If you want the check-in system's notifications to actually send (optional — everything else works without this), generate real keys and add them to `.env`:

```bash
python backend/scripts/generate_vapid_keys.py
```

Then set `BREVO_API_KEY` (free tier, no card required at brevo.com) to enable alert emails too. To allow new accounts, set `BETA_INVITE_CODES` (or `BETA_SIGNUPS_ENABLED=true` for local testing).

## Accounts and private notes

`/account.html` lets someone create a username/password account (no email or phone number required, to avoid recovery flows that could be seen by an abusive person sharing that inbox or phone plan). `/log.html` ("Notes" in the nav, deliberately unlabeled as anything more specific) is a private, per-account notes/evidence log and case-profile page. Content is encrypted client-side in the browser with a separate Notes PIN before it is ever sent to the server — the server and database only ever store ciphertext, never plaintext, and there is no public or cross-account visibility of any of it (there is no "abuser registry" and none is planned; see below).

Real limitations to know before relying on this:
- The Notes PIN has **no recovery path** — if it's forgotten, that content is permanently unreadable, including to the site operator. This is intentional (zero-knowledge design), not a bug.
- There is no file/photo upload yet — text only, partly because photo EXIF metadata can itself leak identifying details like GPS location.
- This has not had a legal review, a security audit, or input from a domestic-violence advocacy organization. Treat it as a technical prototype, not a vetted safety tool, until that review happens. That's why new accounts are invite-only for now.
- A public, crowdsourced "registry of abusers" was deliberately **not** built — it would be a serious defamation and retaliation-safety risk. Only a survivor's own private, non-public case notes exist.

## Check-ins and trusted contacts

`/checkin.html` (linked from Notes & Check-ins) lets a survivor opt in to a check-in schedule and add trusted contacts by email. Miss a check-in past the grace period, and every accepted contact gets an alert by Web Push (instant, free) **and** by email (Brevo's free tier, 300/day), every time: email is not just a fallback. Alerts are numbered and repeat every 6 hours until the survivor checks in, each with a link to `/if-you-get-an-alert.html`; when the survivor checks in (or turns check-ins off) after an alert, contacts get one message saying the alerts have stopped. The survivor can see an alert history (counts only, kept 90 days, clearable) and when each contact's push last worked or was lost. Nothing is sent to anyone until they've explicitly accepted an invite, and they can stop receiving alerts at any time; a contact who stopped can be invited again. See [docs/CHECKIN.md](docs/CHECKIN.md) for the full design, including why SMS isn't part of this (no free option exists) and how invite links work without storing any extra secret.

## Safety Boundaries

This app is not yet an emergency dispatch system. Real-time location sharing, emergency response, partner referral workflows, multi-factor authentication, and any public-facing registry require additional privacy, legal, mobile, reliability, and advocacy-partner design before launch — several of these are intentionally not built yet.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it's built and [docs/PHASE2_PLAN.md](docs/PHASE2_PLAN.md) for what's next.
