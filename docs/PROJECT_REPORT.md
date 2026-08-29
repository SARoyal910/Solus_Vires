# Solus Vires — Project Report

**As of:** 2026-08-29
**Status:** Technical prototype. Not yet reviewed by legal counsel or a domestic-violence advocacy organization — see [TODO.md](TODO.md) before any real-world use.

This report covers everything built in this codebase to date, in two layers for every section: **In plain terms** (what it does and why, no jargon) and **Technically** (how it's actually built, for anyone picking up the code). Companion docs with more depth are linked throughout.

---

## 1. What Solus Vires is

**In plain terms:** Solus Vires is a website for people affected by domestic abuse. It gives free access to real crisis hotlines, legal aid, and mental-health resources; a private space to keep notes that only the survivor can read, even if the site itself were ever hacked or subpoenaed; and a way to have a trusted friend automatically notified if the survivor goes quiet when they shouldn't.

**Technically:** A FastAPI backend (Python) serving a JSON API, paired with a dependency-free static frontend (plain HTML/CSS/JS, no build step, no framework). Postgres via SQLAlchemy + Alembic migrations. Nginx reverse-proxies HTTPS traffic to the API and serves static files directly. The whole stack runs via Docker Compose. No paid third-party services are required to run any feature — a constraint that shaped several design decisions below.

---

## 2. Foundation — public pages and contact intake

**In plain terms:** Before any of this session's work, the site already had informational pages (Resources, Safety Planning, Legal, Partners, Emergency) and a contact form. The form only confirmed receipt — it wasn't yet connected to anyone who could act on it.

**Technically:** `backend/app/api/contact.py` + `services/contact.py` handle `POST /api/contact`; deliberately never logs message content, only structural metadata (message length, whether optional fields were filled). Static pages live in `html/`, served by nginx in Docker and by FastAPI's `StaticFiles` mount in local dev.

---

## 3. Accounts and private notes (built prior to this session)

**In plain terms:** A survivor can create an account with just a username and password — no email or phone number, because a shared inbox or phone plan is exactly the kind of thing an abusive partner might also have access to. Once logged in, they can open "Notes" (deliberately labeled something generic, not "Evidence Log," so a glance at a browser tab gives nothing away), set a separate PIN, and write private entries. Those entries are encrypted *in the browser* before they're ever sent anywhere — the server only ever stores scrambled data it cannot read. If the PIN is forgotten, the notes are gone permanently, even to whoever runs the site. That's intentional: it's the only way "we can't read your notes" can be a real promise instead of a policy.

**Technically:** `User`/`Session`/`RecoveryCode` models (`backend/app/models/auth.py`); Argon2id for password hashing, opaque SHA-256-hashed session tokens in `httponly`/`SameSite=Strict` cookies (not JWT, specifically so `/api/auth/logout-all` gives instant, real revocation). `CaseProfile`/`EvidenceEntry` models (`models/evidence.py`) store only `ciphertext` + `iv` — no plaintext field of any kind. Client-side crypto in `html/evidence-crypto.js`: PBKDF2-SHA256 (≥600,000 iterations) derives an AES-256-GCM key from the PIN + a per-user salt; the key is a non-extractable `CryptoKey` living only in memory, re-derived on every page load. Full detail and the verification history (including a real bug found and fixed — a wrong PIN silently unlocking the page) in [ACCOUNTS_AND_NOTES.md](ACCOUNTS_AND_NOTES.md).

---

## 4. Visual redesign (this session)

**In plain terms:** The whole site got a design pass — the earlier version worked but looked like a generic template. It now has a consistent, modern look across every page: a confident gradient hero on the homepage, better typography, cards with a bit of color and depth, smooth hover states, and a small brand mark. The goal was to feel trustworthy and a little hopeful, not clinical or cold — without ever undermining the site's core safety features (Quick Exit stayed instant and unmissable; nothing about the redesign makes the site look more "distinctive" in a way that could out someone glancing at a shared screen).

**Technically:** Full rewrite of `html/shared.css` — new design tokens (color, radius, shadow, motion-timing scale), a component system (`.card`, `.btn`, `.hero`, `.trust-chip`, etc.) reused identically across all pages so changes cascade from one file. `prefers-reduced-motion` respected throughout. No external font or icon requests — everything is system fonts plus small inline SVGs (including the brand mark), consistent with the project's existing "no unnecessary third-party network calls" posture. Applied consistently to all ~13 HTML pages via targeted batch edits to the shared header/nav markup.

---

## 5. Verified resource content

**In plain terms:** Several pages used to have placeholder text like "future partner records" or a handful of links. They now list real, currently-operating, mostly-free organizations — national hotlines, legal aid groups, and population-specific support (LGBTQ, trans, male survivors, immigrants, elders, trafficking victims, military). Every phone number, text shortcode, and URL was actually looked up and checked against the organization's own site before it went on the page — not pulled from memory. A few honest caveats are called out directly in the copy instead of glossed over: one resource costs money despite looking free-adjacent, two aren't available 24/7, and one has no phone line at all.

**Technically:** A research pass (via a dedicated subagent using live web search/fetch, not model recall) produced a sourced table of organizations, cross-checked against official `.org`/`.gov` domains. Every resulting `href`, phone number, and SMS shortcode across `resources.html`, `legal.html`, `emergency.html`, and `recovery.html` was diffed against that table before publishing (verified via `grep` cross-check in this session, not just visual review). Caveats preserved verbatim in the UI: Open Path Collective is low-cost, not free ($65 + $30–80/session); NAMI's HelpLine and the Eldercare Locator are not 24/7; 1in6 is chat-only, no phone number exists.

---

## 6. Recovery & Wellness page

**In plain terms:** A new page offers a plain-language explanation of a well-established trauma-recovery framework (safety → processing what happened → rebuilding), plus tools someone can actually use in the moment: a guided breathing exercise, a 5-senses grounding exercise, and short, non-generic reminders. It also links out to real free/low-cost mental-health resources. Nothing typed into the tools is saved anywhere; a simple "what have I explored" checklist is remembered only on that device.

**Technically:** `html/recovery.html` + `recovery.js`, fully client-side, zero backend involvement. The trauma-recovery framework cited (Judith Herman's three-stage model) was verified as a legitimate, peer-reviewed clinical model before being described on the page. Interactive tools are plain JS: a `setTimeout`-driven box-breathing state machine, a stepper for the grounding exercise, an affirmation rotator. Progress tracking uses `localStorage` only — no network calls, no cost, no server-side trace.

---

## 7. Trusted-contact "I'm OK" check-in system

**In plain terms:** A survivor can opt in to a check-in schedule (e.g., every 24 hours) and add a trusted contact by email. If they don't check in within their chosen window, that contact gets an alert — an instant notification if they've enabled it on their device, and an email either way as backup. Nothing happens until the contact explicitly accepts the invite, and they can opt out at any time with one click. This directly replaces what would normally cost real money (text-message alerts) with something that costs nothing to run, without pretending it's exactly as instant or guaranteed as SMS would be.

**Technically:** Three new tables (`TrustedContact`, `PushSubscription`, `CheckinSchedule`) and a `checkin` API router (survivor-authenticated contact/schedule management, plus public token-authenticated invite endpoints for the contact, who never has an account). Alerts use Web Push (VAPID, genuinely free, no message cap) as the primary channel and Brevo's email API (permanent free tier, 300/day) as fallback — both no-op gracefully when unconfigured rather than erroring. A background `asyncio` task in the app's `lifespan` (no new scheduler dependency) checks for overdue schedules every 5 minutes by default.

One real design correction made mid-build: invite links can't be a one-way-hashed, verify-only secret like a session token, because the *server* needs to re-embed the same working link in emails sent long after the original token would have been discarded (a missed-check-in alert, sent potentially days later). Solved with a stateless HMAC-signed token (`contact_id + HMAC-SHA256(secret, contact_id)`) — nothing extra is stored, and the exact same link can be regenerated forever. Full design writeup and the end-to-end verification log (invite → accept → subscribe → forced-overdue → alert fire → check-in reset → contact self-revoke, all run against the live Docker stack) in [CHECKIN.md](CHECKIN.md).

---

## 8. Full account deletion

**In plain terms:** Until now, a survivor could delete individual notes or contacts one at a time, but there was no single "erase everything and leave no trace" button. There is now — it requires re-typing your password and checking a confirmation box (so a hijacked session or a curious passerby can't wipe an account by accident), and it's genuinely permanent: notes, case profile, trusted contacts, and login sessions are all gone in one step, even from the server's own database.

**Technically:** `POST /api/auth/delete-account` — password re-verified via Argon2, then `db.delete(user); db.commit()`. Every child table's foreign key is already `ondelete="CASCADE"` (sessions, recovery codes, case profile, evidence entries, trusted contacts → push subscriptions, check-in schedule), so deleting the `User` row is genuinely sufficient — no separate cleanup code needed, no risk of it silently missing a table. Verified against the live database: wrong password correctly rejected with zero rows touched; correct password removed every related row (confirmed via direct SQL count before/after); the session cookie died immediately; the old password stopped working on a subsequent login attempt.

---

## 9. Infrastructure fix — local dev vs. Docker database split

**In plain terms:** A real bug surfaced while testing: logging in worked when testing through the live Docker version of the site, but failed on the separate local development server, because they were quietly talking to two completely different databases on the same machine — one of which didn't even have the right setup. That's now fixed; both point at the exact same data.

**Technically:** The Docker Compose `db` service previously used `expose` only (container-network-internal), so a locally-run `uvicorn` process fell through to whatever Postgres happened to be listening on the host's default port 5432 — in this case, an unrelated Homebrew Postgres instance used for other projects. Fix: `db` now also publishes to `127.0.0.1:5433` (loopback-only — never reachable off the host, and deliberately not the default port so it can't collide with a pre-existing local Postgres installation). `.env`/`.env.example`'s `DATABASE_URL` updated to match. Verified: the same `devuser` login now succeeds identically through both `https://localhost` (Docker/nginx) and `http://127.0.0.1:8000` (local `uvicorn`).

---

## 10. What's been verified vs. what hasn't

Everything above with a "verified end-to-end" claim was tested against the real running Docker stack (rebuilt image, live Postgres, real HTTP requests through nginx) — not just confirmed to import cleanly. That said, several things are still unverified in the way that matters most:

- No real push notification has reached an actual device (only a fake endpoint has been exercised)
- No real email has been sent via Brevo (no API key is configured in this dev environment, by design)
- The iOS "Add to Home Screen" push flow hasn't been tried on a real iPhone
- The background alert loop has only been triggered manually, not observed firing on its own timer

See [PROGRESS.md](PROGRESS.md) for the full verified/not-yet-verified breakdown.

---

## 11. What's still needed before this touches a real survivor

This remains a technical prototype. In priority order:

1. **Legal review** — privacy, mandatory-reporting exposure, emergency-language claims. Nothing else on this list substitutes for this.
2. **A formal threat model** — DV-tech safety practices were followed throughout (no email/SMS recovery, zero-knowledge notes, instant session revocation, generic page labeling, consent-first check-in invites), but there's been no structured, adversarial review of the design.
3. **Input from an actual DV advocacy organization** — on copy, flows, and the check-in system's failure modes specifically.

The full, actionable punch list — including security hardening, unbuilt features (real-time location sharing, MFA, partner tooling), and smaller rough edges — is in [TODO.md](TODO.md).
