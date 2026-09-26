# Progress

The one status page: what exists and is live right now. Detail lives in each feature's own doc; Phase 2 work in progress is tracked ticket by ticket in `docs/PHASE2_PLAN.md`.

**Last verified against production:** 2026-09-26, `main` at `83d1f08` on the droplet (live header probe green on all 21 checked paths, CI green).

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

## On the `phase2` branch, not yet deployed

- Browsers revalidate pages on every visit (`Cache-Control: no-cache`), so nobody sees a stale copy
- Runbook note on the Cloudflare settings the site depends on

## Verified vs. not yet verified

Verified: the full check-in round trip against a real stack (`docs/CHECKIN.md`); Notes PIN flows in real Chrome (`tests/browser/notes_pin.mjs`, 16/16); a production backup decrypted and restored; the live site's headers, sign-up gate, and origin lock.

Not yet verified in the real world:
- A push notification delivered to a real phone, and the iOS "Add to Home Screen" flow
- A real email delivered via Brevo
- The alert loop firing on its own timer (only triggered manually)
- That access logging is off on the droplet (owner to check `docker logs solusvires_web`)

## Not done yet

See `docs/PHASE2_PLAN.md` for the full list and order. Highlights: legal review and advocacy review, a monitored contact address, Spanish review, a Content Security Policy, notes export, Quick Exit v2, and the low-key theme.
