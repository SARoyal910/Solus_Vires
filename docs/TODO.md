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

- [ ] Rate limiting and abuse detection — currently only basic login lockout exists; no CAPTCHA, no rate limits on the public check-in invite endpoints (`/api/checkin/invite/{token}/*`)
- [ ] Backup/restore testing for Postgres (migrations exist; restore has never been exercised)
- [ ] Retention/deletion policy — evidence entries and trusted contacts can be deleted by the user, but there's no defined retention window or full account-deletion flow
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
- [ ] Local (non-Docker) dev server story is currently a bit rough — the checked-in `.env` local `DATABASE_URL` and the Docker Compose Postgres are two different databases on this machine; worth deciding on one dev workflow
