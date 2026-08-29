# Progress

A running snapshot of what exists in this repo right now. Deep detail for each feature lives in its own doc — this is the index.

## Built and working

**Phase 1 — public foundation**
- Static public pages (`html/`), FastAPI backend, nginx + Docker Compose skeleton
- Contact form (`/contact.html` → `/api/contact`) — receipt-only, no real intake pipeline yet

**Phase 2 — accounts and private notes** (`docs/ACCOUNTS_AND_NOTES.md`)
- Username/password accounts, opaque DB-backed sessions, recovery codes, login lockout
- `/log.html` ("Notes"): PIN-locked, client-side AES-GCM encrypted notes/case-profile — server only ever stores ciphertext

**Visual design system**
- Full redesign of `shared.css` (type scale, color, motion, cards, buttons) applied consistently across every page
- Redesigned homepage hero, unified nav/header/footer across all 9+ pages

**Verified resource content**
- `resources.html`, `legal.html`, `emergency.html` — every hotline/org/link was verified against its own official source (not reconstructed from memory) before publishing; see caveats noted inline (e.g., Open Path Collective is low-cost not free, NAMI HelpLine isn't 24/7)

**Recovery & Wellness** (`html/recovery.html`)
- Trauma-informed recovery framework (Herman's three-stage model)
- Fully working interactive tools: box breathing, 5-4-3-2-1 grounding, grounding reminders — all client-side, `localStorage` progress only
- Verified free/low-cost mental-health resource directory

**Trusted-contact check-in system** (`docs/CHECKIN.md`)
- Opt-in "I'm OK" schedule with a background alert loop (no new infra — an `asyncio` task in the app lifespan)
- Web Push (free, VAPID) as the primary alert channel, Brevo email (free tier) as fallback
- Consent-first invite flow; stateless HMAC-signed invite links (nothing extra stored)
- Verified end-to-end against the real Docker stack: invite → accept → subscribe → forced-overdue → alert fire → check-in reset → contact self-revoke

## Verified vs. not yet verified

Verified this session: full check-in round trip against the live Postgres + nginx stack (see `docs/CHECKIN.md` for the exact steps run).

Not yet verified — real-world, not just code-path:
- An actual push notification delivered to a real device (only a fake endpoint was exercised)
- An actual email delivered via Brevo (no `BREVO_API_KEY` set in dev, by design)
- The iOS "Add to Home Screen" push flow on a real iPhone
- The background alert loop firing naturally on its own timer (only triggered manually)

## Not built yet

See `docs/TODO.md` for the actionable list. Highlights: real-time location sharing, SMS as a channel (no free option exists), MFA, partner-facing tooling, legal review, formal threat model.
