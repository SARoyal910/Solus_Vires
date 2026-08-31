# TODO

Actionable punch list, pulled together from the "not done" / "not yet verified" items scattered across `ARCHITECTURE.md`, `CHECKIN.md`, and `README.md`. Roughly ordered by what would unblock real (non-prototype) use soonest.

## Before this touches a real survivor

- [ ] **Legal review** — privacy, mandatory-reporting exposure, emergency-language claims. Hard prerequisite per README; nothing below substitutes for this.
- [ ] **Formal threat model** — this was built with DV-tech safety practices in mind (no email/SMS account recovery, zero-knowledge evidence encryption, instant session revocation, generic page labeling, consent-first check-in invites) but has never had a structured threat-modeling pass.
- [ ] **Input from an actual DV advocacy organization** — on copy, flows, and the check-in system's design specifically (a missed-check-in alert is a new kind of risk surface — e.g., false negatives if push silently stops working).

## Check-in system — real-world verification

- [ ] Send a real Web Push notification to a real device (only a fake endpoint has been exercised so far)
- [ ] Send a real email via Brevo (`BREVO_API_KEY` is unset in dev by design — set it and confirm delivery)
- [ ] Walk through the iOS "Add to Home Screen" push flow on an actual iPhone
- [ ] Let the background alert loop fire naturally on its timer instead of triggering it manually
- [ ] Decide whether a stale/dead push subscription should also *tell the survivor* their contact's push silently broke, not just prune it server-side

## Security / production hardening

- [ ] CAPTCHA on public unauthenticated endpoints (register, contact, check-in invite links) — the rate limiter added below caps brute-force volume but doesn't stop a slow, patient attacker
- [ ] Real abuse-detection/alerting (e.g. paging someone when a single IP is hitting the rate limit repeatedly) — right now a capped attacker just gets a 429, nobody is told
- [ ] Backup/restore testing for Postgres (migrations exist; restore has never been exercised)
- [ ] Retention *window* policy — full account-deletion now exists (see below), but there's still no defined default retention period for data a user hasn't manually deleted
- [ ] Audit logging — deliberately deferred (logging login IPs etc. is itself a risk to design carefully, not bolt on) but worth a real decision, not just a default of "nothing"
- [ ] MFA — single-factor auth only right now

## Features explicitly not built

- [ ] Real-time location sharing — bigger and more safety-sensitive than the check-in system; needs its own opt-in, tested design per `ARCHITECTURE.md`'s location/emergency principles before it's touched
- [ ] File/photo evidence upload (photo EXIF can leak GPS — needs a stripping step first)
- [ ] Partner-facing tooling / RBAC — no partner access exists yet; `partners.html` is still a roadmap page
- [ ] A disguised/skinned UI beyond generic page labeling (e.g., a weather-app-style disguise) — considered and scoped out, not forgotten

## Smaller/nice-to-have

- [ ] Let a survivor resend an invite to a contact who self-revoked without having to delete and re-add them (currently blocked with a 409 — workable since the contact can still re-accept their original link, but a rough edge)
- [ ] A history/audit view for the survivor of when alerts actually fired

## Done since last pass

- [x] Local (non-Docker) dev server now shares the exact same Postgres as Docker — `docker-compose.yml` publishes `db` on `127.0.0.1:5433` (loopback-only, non-default port so it never collides with a locally-installed Postgres), and `.env`/`.env.example`'s `DATABASE_URL` point there. Previously the local `uvicorn` workflow silently connected to a different, unmigrated Postgres.
- [x] Per-IP rate limiting on the public/unauthenticated endpoints that had none — `POST /api/auth/register` (5/hour), `POST /api/auth/login` (20/5min, on top of the existing per-account lockout), `POST /api/auth/recover` (10/hour), `POST /api/contact` (5/10min), and all `GET|POST /api/checkin/invite/{token}/*` routes (30/5min shared across all five of those routes per IP, not 30 each - they use one limiter instance). In-process sliding-window limiter (`backend/app/core/rate_limit.py`), keyed by the real client IP that nginx sets in `X-Real-IP`. Deliberately simple and single-process only — matches the single-uvicorn-worker deployment today, but would need a shared store (e.g. Redis) before scaling to multiple workers/instances. CAPTCHA and active abuse alerting are still not done (see above).

- [x] Full account-deletion flow — `POST /api/auth/delete-account` (password re-confirmation required) permanently deletes the user and everything tied to it (notes, case profile, trusted contacts, push subscriptions, sessions) via cascading foreign keys. UI on `account.html` behind an explicit reveal + checkbox, not a single accidental click. Verified end-to-end against the real Docker stack: wrong password correctly rejected with nothing deleted, correct password deletes everything, session dies immediately, old credentials rejected afterward.
