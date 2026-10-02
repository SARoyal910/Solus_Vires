# Trusted-Contact Check-In System — Implementation Notes

Documents the "I'm OK" check-in and missed-check-in alert feature: why it exists, what was built, and the free-tier notification design behind it. Companion to [ARCHITECTURE.md](ARCHITECTURE.md) and [ACCOUNTS_AND_NOTES.md](ACCOUNTS_AND_NOTES.md).

## Why this exists

`docs/ARCHITECTURE.md` and the README both flagged a trusted-contact "I'm OK" check-in system as the next planned phase after accounts + private notes. This pass builds it: a survivor can opt in to a check-in schedule, add trusted contacts, and have those contacts automatically alerted if a check-in is missed.

## The cost constraint that shaped the design

The project has an explicit "keep production free" constraint. That ruled out SMS as the notification channel — every SMS provider (Twilio, Vonage, AWS SNS) charges per message, and trial credits aren't viable for real production use (Twilio trial accounts can only message pre-verified numbers). Instead, this feature uses two channels that are genuinely free at this scale:

- **Web Push** (primary) — the W3C Push API + VAPID, with no third-party service or per-message cost. On Android, Chrome routes it through Firebase Cloud Messaging in the background; on iOS 16.4+, if the contact adds the site to their home screen, it routes through Apple's APNs. Requires the contact to visit an invite link once and grant notification permission — and on iOS specifically, to add the page to their home screen first, since plain Safari tabs can't receive push at all.
- **Email via Brevo** — Brevo's transactional email API has a genuine permanent free tier (300 emails/day, no credit card). Sent on **every** alert alongside push, not only when push fails: push delivery isn't guaranteed (a subscription can go stale, or a device can be offline long enough that the push service drops the message), and a duplicate alert is safer than a missed one (Phase 2 decision D4). Each alert says it repeats every `CHECKIN_ALERT_REPEAT_HOURS` (6) until the survivor checks in, and links to `/if-you-get-an-alert.html`.

Both are skipped gracefully (logged, not an error) when their config isn't set — same pattern as `CONTACT_SINK=console` elsewhere in this codebase — so local development doesn't require real API keys.

## Consent, not surveillance

This is explicitly the kind of feature `ARCHITECTURE.md` warns about: "must be opt-in, transparent, tested, and connected to trusted response partners before launch." Concretely:

- A check-in schedule is off by default; the survivor has to turn it on.
- A trusted contact is only added by the survivor entering their email — the contact then gets an explicit invite and must actively **accept** before anything is ever sent to them. Nothing is silent.
- The contact only ever sees the survivor's username (already chosen to be non-identifying), never the survivor's private nickname for them, never any note or evidence content.
- The contact can stop receiving alerts at any time via a link in every email, with no back-and-forth required.
- There is no location sharing in this pass — only "did they check in or not." Real-time location sharing remains explicitly out of scope until it gets its own opt-in, tested design (per `ARCHITECTURE.md`).

## Invite links: a stateless, HMAC-signed token, not a stored secret

Session tokens and recovery codes elsewhere in this codebase are hashed and stored verify-only, because the server only ever needs to check what the client presents back. The check-in invite link is different: the **server itself** needs to re-embed a working link in emails sent long after the contact row was created (the initial invite, a resend, and — much later — a missed-check-in alert). A one-way hash can't be reversed to reconstruct that link.

Instead, `backend/app/services/checkin.py` derives the token deterministically: `HMAC-SHA256(CHECKIN_TOKEN_SECRET, contact_id)`, with the contact id embedded alongside the signature in the URL (`{contact_id}.{signature}`). Nothing extra is stored — the exact same link can be regenerated forever from the contact's id, and a forged token fails the constant-time signature comparison. Revocation is handled by status (`pending` / `accepted` / `declined` / `revoked`) rather than by expiring the token itself.

## Data model

Three new tables, added via Alembic migration `backend/migrations/versions/0002_checkin.py`:

```
trusted_contacts   id, user_id (fk), nickname, contact_email, status,
                   invited_at, responded_at, created_at

push_subscriptions id, trusted_contact_id (fk), endpoint (unique per contact), p256dh, auth,
                   created_at, last_seen_at

checkin_schedules  id, user_id (fk, unique — one per account), active,
                   interval_hours, grace_hours, last_checkin_at,
                   next_deadline_at, last_alert_sent_at, created_at, updated_at
```

`nickname` is the survivor's own private label for the contact and is never sent to the contact or exposed by any public endpoint.

**One device, several survivors (Phase 2, migration 0004).** A browser has one push endpoint per site. Endpoints used to be globally unique, so a person who was the trusted contact for two survivors had their device silently moved to whichever invite they subscribed under last. Endpoints are now unique per contact: the same device can serve several contacts, re-subscribing refreshes its keys under all of them, and an expired endpoint is removed from all of them.

## API surface

**`backend/app/api/checkin.py`** (`CheckinService` in `backend/app/services/checkin.py`):

Survivor-authenticated (behind `get_current_user`, scoped to the caller):
- `GET/POST /api/checkin/contacts`, `DELETE /api/checkin/contacts/{id}`, `POST /api/checkin/contacts/{id}/resend`
- `GET/PUT /api/checkin/schedule`, `POST /api/checkin/schedule/checkin` ("I'm OK")

Public, token-authenticated (no account — this is the first place in the app where someone other than the account holder interacts with the backend):
- `GET /api/checkin/invite/{token}` — survivor's username + current status only
- `POST /api/checkin/invite/{token}/accept`, `/decline`, `/stop`
- `POST /api/checkin/invite/{token}/subscribe` — registers a Web Push subscription
- `GET /api/checkin/vapid-public-key` — the public half of the VAPID keypair (safe to expose; the private half never leaves the server)

## Background alert loop

No new infrastructure or scheduler dependency: `backend/app/main.py` starts a single `asyncio` background task in the app's `lifespan` context that sleeps for `CHECKIN_ALERT_CHECK_SECONDS` (default 300s), then runs one pass over active schedules in a thread (`asyncio.to_thread`) so the synchronous DB/HTTP work in `CheckinService.run_due_alerts_once` doesn't block the event loop. A pass that raises is logged and the loop carries on; it never silently stops.

- **One pass at a time (Phase 2, P2-A8).** Each pass holds a Postgres advisory lock (`pg_try_advisory_lock`, on its own connection) for its whole run. A second process pointed at the same database, such as a local `uvicorn` next to the Docker `api`, skips the pass instead of sending duplicate alerts. `CHECKIN_ALERT_LOOP_ENABLED` turns the loop off entirely; it defaults to on only when `APP_ENV=production`.
- **When an alert fires.** A schedule is overdue once `next_deadline_at + grace_hours` has passed. Alerts repeat at most every `CHECKIN_ALERT_REPEAT_HOURS` (default 6) until the survivor checks in again, rather than firing once or spamming continuously.
- **Both channels, every time (decision D4).** Every accepted contact gets a push to each of their subscribed devices (a 404/410 response prunes that device for every contact it served) **and** an email, on the first alert and on every repeat. Email is not a fallback that only runs when push fails: the server can never confirm a push was seen, and a duplicate alert is safer than a missed one.
- **The copy says what happens next.** Both the email and the push say the alert repeats every `CHECKIN_ALERT_REPEAT_HOURS` hours until the survivor checks in, and point to `/if-you-get-an-alert.html`.
- **Saving the schedule moves the deadline (P2-A11).** While check-ins are on, every save recomputes `next_deadline_at = last_checkin_at + interval_hours`, so shortening the interval takes effect at once. If that time has already passed, the deadline is set to the moment of saving and the grace period runs from there.

## Frontend

- **`html/checkin.html`** — survivor-facing: schedule on/off + interval/grace period, "I'm OK" button, add/remove/resend trusted contacts. Linked from `account.html` ("Manage check-ins") and `emergency.html`, not from the main nav — same discoverability pattern as `log.html`.
- **`html/checkin-invite.html`** — the contact-facing page for every state (pending/accepted/declined/revoked/invalid token), including the push opt-in flow with an explicit iOS "Add to Home Screen" instruction when needed.
- **`html/sw.js`** — the service worker, registered only from the contact's browser (`checkin-invite.js`), handling `push` and `notificationclick`.
- **`html/checkin.js`**, **`html/checkin-invite.js`** — plain JS, no build step, matching the rest of this codebase.

## What was verified

Against the real Docker stack (`docker compose build api && docker compose up -d api`), through nginx at `https://localhost`, not a direct backend call:

- Migration applied cleanly to the running Postgres; all three tables confirmed via `\dt`.
- Full round trip: registered a test account, added a trusted contact, fetched the invite by reconstructing its HMAC token, accepted it, registered a (fake) push subscription, activated a schedule, forced it overdue by rewriting `next_deadline_at`, and ran the alert pass directly — it attempted the push (failed gracefully and predictably on the fake endpoint, logged rather than crashing), attempted the email fallback (no-op logged since `BREVO_API_KEY` wasn't set), and correctly set `last_alert_sent_at`.
- "I'm OK" check-in correctly reset the deadline and cleared the overdue state.
- The contact's own "stop being a check-in contact" endpoint correctly revoked status and deleted their push subscriptions.
- `resend` correctly rejected (409) for an already-responded contact, since the original invite link stays valid — the contact can always re-accept it directly, so a resend is unnecessary once they've replied.
- An invalid/forged token correctly returned 404 from the invite endpoint.
- Test account and contact were deleted from the dev database afterward.

## Not yet verified

- A real push notification delivered to an actual device (the fake endpoint above only proves the send path and error handling, not real delivery through FCM/APNs).
- A real email delivered via Brevo (`BREVO_API_KEY` is unset in this dev environment by design, to keep local dev free of external calls).
- The iOS "Add to Home Screen" push flow in an actual iOS browser.
- The background alert loop's natural (non-manual) firing on its real interval.

## Explicitly deferred — not built in this pass

- Real-time location sharing (a separate, larger, and more safety-sensitive feature than a check-in ping — deliberately not bundled in).
- SMS as a channel (no free option exists; see above).
- Rate limiting on invite creation or the public invite endpoints.
- A UI for the survivor to see *why* an alert fired (e.g., a history log) beyond the current overdue/not-overdue state.
