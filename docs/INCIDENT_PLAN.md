# Incident plan

**Ticket:** P2-F5. **Written:** 2026-10-02 against `phase2` at `83be254`. Read with `docs/THREAT_MODEL.md` (what can go wrong) and `docs/RUNBOOK.md` (how to deploy, back up, restore, monitor).

**Who does what.** There is one operator: **Steven Royal** (Omnia Royal LLC), who has the droplet, the Cloudflare and DigitalOcean accounts, Brevo, and the offline backup key. Every "you" below is him. Until a second person is named here, nobody covers for him when he's unreachable; that is a known gap, listed at the end.

**What we can and can't do for survivors.** We hold no email address or phone number for survivors, by design. **We cannot contact a survivor directly.** We can only (1) put a notice on the site, which they see when they visit, and (2) email trusted contacts, which we do only for alerts and never to discuss a survivor. Every plan below works within that.

---

## Severity

| Level | Means | Examples | Respond |
|---|---|---|---|
| **S1** | Survivor data may be exposed, or the site is serving something harmful | Database or backup stolen; droplet compromised; site serving injected script or a wrong crisis number | Drop everything, start within the hour |
| **S2** | A safety feature is silently not working | Alert loop stopped; email or push not delivering; API down while pages still load | Same day |
| **S3** | Degraded, nobody at risk | Site slow; one page broken; CI red | Next working session |

## First hour, any S1

1. **Write down the time and what you saw** in a private note (not in the repo yet). Times matter later.
2. **Don't wipe anything.** Snapshot the droplet first (DigitalOcean > Droplet > Snapshots); it preserves evidence and a way back.
3. **Contain** using the scenario below.
4. **Put up the notice** for that scenario (wording below). Honest, short, no speculation.
5. Within 24 hours: ask counsel whether any notification law applies (question already in `docs/legal/`), and write the incident up in `docs/incidents/YYYY-MM-DD.md` (what happened, what was exposed, what changed). Leave out anything that identifies a user.

---

## Scenario 1 · Database or backup breach (S1)

*Signs:* a dump turns up somewhere; DigitalOcean reports a breach; Postgres shows connections or roles you didn't make; a backup file or the backup key leaves your control.

**What an attacker has** (from `docs/THREAT_MODEL.md` A3): usernames, password hashes (Argon2id), recovery-code hashes, contacts' nicknames and emails, check-in schedules and times, push endpoints, timestamps, and notes **only as ciphertext**. Notes under a strong PIN are safe; notes under a short pre-2026-09-26 PIN may be guessable with effort.

**Contain**
1. End every session: `docker compose exec db psql -U solusvires -d solusvires -c 'DELETE FROM sessions;'`
2. Rotate secrets in the droplet's `.env`, then `docker compose up -d --wait`:
   - `POSTGRES_PASSWORD` (also `ALTER USER solusvires PASSWORD '...'` in psql first, or the api can't connect).
   - `CHECKIN_TOKEN_SECRET`. This invalidates every invite and "manage alerts" link already emailed. Contacts who already accepted keep getting alerts; the next alert email carries a working link.
   - `BREVO_API_KEY` (create a new key in Brevo, delete the old one).
   - **Not** `RECOVERY_CODE_PEPPER`, unless the attacker could also read the droplet's `.env` (Scenario 2). The pepper is what makes the recovery-code hashes in a stolen dump useless on their own. Changing it makes every recovery code stop working, and there is no way yet for someone to make new ones.
3. If the **backup key** leaked, every backup is readable: generate a new `age` key (`docs/RUNBOOK.md` "Backups"), switch the droplet's recipient, take a fresh backup, delete old backups everywhere you can.
4. If the attacker had a shell on the droplet, treat it as Scenario 2 as well.

**Tell people.** Notice at the top of `/index.html`, `/about.html` and `/account.html`:
> *[Date]: Someone got a copy of this site's database. Your notes were stored encrypted with your PIN, which we never had, so they can't be read without it. They could see usernames, trusted contacts' email addresses, and check-in times. Everyone has been signed out. If your notes PIN is short or easy to guess, assume someone could eventually read those notes. If you're worried about your safety, call the National Domestic Violence Hotline: 1-800-799-7233, or text START to 88788.*

Keep it up for at least 90 days: people may come back rarely. If the operator's own mailbox was also breached, contact-form messages were exposed too: say so in the notice. Do **not** email trusted contacts about the breach unless counsel advises it: an email out of the blue tells a contact's household that someone they know uses this site.

## Scenario 2 · Droplet or account compromise (S1)

*Signs:* unknown SSH keys or processes; changed files in the checkout (`git status` dirty); a page that doesn't match the repo; a login alert from DigitalOcean, Cloudflare, GitHub, or Brevo you didn't cause.

**Contain**
1. In Cloudflare, turn on **Under Attack** mode or pause the site if pages are altered (a down site is better than a malicious one: crisis numbers are also at thehotline.org).
2. Change passwords and 2FA on DigitalOcean, Cloudflare, GitHub, Brevo, and the email account that resets them. Revoke unknown SSH keys and API tokens.
3. **Build a new droplet** from a clean image rather than cleaning the old one. Fresh checkout of `main`, new `.env` with all secrets rotated (Scenario 1 step 2, plus `RECOVERY_CODE_PEPPER`, since the attacker may have read it: every existing recovery code stops working, so the notice must say so; plus new VAPID keys: `python backend/scripts/generate_vapid_keys.py`; contacts have to turn notifications on again from their invite page). Restore the latest backup you trust (`docs/RUNBOOK.md` "Real restore"), from *before* the compromise.
4. New Cloudflare Origin certificate; revoke the old one.
5. Point Cloudflare at the new droplet, run `scripts/smoke.sh https://solusvires.com`, then destroy the old droplet once its snapshot is kept.

**Tell people:** as Scenario 1, adding: *"The site's server was broken into. Anything typed into the site between [dates] may have been seen, including passwords and notes PINs. Change your password. A notes PIN can't be changed without losing the notes, so if you opened your notes during that time, copy anything you need somewhere safe and think about starting a new account."* Let counsel review this one before posting if at all possible.

## Scenario 3 · The site is serving something harmful (S1)

*Signs:* `scripts/smoke.sh` step 5 fails (a third-party script appeared); a visitor reports a strange page; a crisis number on the site is wrong or out of date.

- **Injected script** (usually a Cloudflare feature turned back on: Web Analytics, Rocket Loader, Zaraz): turn it off in Cloudflare, purge the cache, re-run smoke. If the script isn't from Cloudflare, treat as Scenario 2.
- **Wrong number or dead organization:** fix the page from the organization's own website, deploy the same day, purge Cloudflare's cache. A wrong hotline number is the most harmful content error this site can make. Search every page, including `/es/`, for the same number.
- Notice only if it was live for more than a day: a line on the affected page saying what changed and when.

## Scenario 4 · Check-in alerts stopped (S2)

*Signs:* Healthchecks.io says the alert-loop heartbeat is late (`docs/RUNBOOK.md` "Monitoring"); `docker compose ps` shows the api unhealthy or restarting; Brevo shows errors or the daily limit reached; a contact reports getting nothing.

**Why it's serious:** a survivor who set up check-ins is relying on someone being told if they go quiet. Missed alerts can't be sent late in a meaningful way.

**Contain**
1. `docker compose ps` and `docker compose logs --tail 100 api`. Unhealthy because of the schema: `scripts/migrate.sh`, then `docker compose up -d --wait`. Otherwise `docker compose restart api`.
2. The loop runs inside the api process. A restart starts it again; overdue survivors are alerted on the next pass (default within 5 minutes), because alerts depend on stored deadlines, not on the loop having been running.
3. Brevo limit hit (300 emails a day on the free plan): alerts still go by push. Find what used the quota (invite emails, a loop sending repeatedly) and fix it.
4. Note the window: from the last good heartbeat to the fix.

**Tell people.** If the outage was longer than the shortest grace period anyone could have set (zero hours is allowed, so: any outage longer than one alert pass), put a notice on `/checkin.html`, `/account.html` and `/if-you-get-an-alert.html`:
> *Check-in alerts weren't being sent between [time] and [time] [timezone]. They're working again. If you missed a check-in during that time, your contacts may not have been told. Check in now, and if you rely on check-ins, let your contacts know.*

## Scenario 4b · Abuse alert email (S3)

*Signs:* an email "repeated rate-limit hits from one address" (`OPERATOR_ALERT_EMAIL`). The limits are already refusing that address; the email carries counts and paths, never the address (none is kept). If it repeats daily or targets `/api/auth/login`, add a Cloudflare rate-limiting or WAF rule for that path. No notice to users.

## Scenario 5 · Site or API down (S2/S3)

*Signs:* UptimeRobot alert. Pages down: check Cloudflare status, then the droplet (`docker compose ps`), then disk (`df -h`; Docker logs are capped, backups keep 30). API down but pages up: S2, because Notes and check-ins are unavailable; Scenario 4 step 1. If the api keeps restarting and `docker compose logs api` shows `refusing_to_start:`, a required secret in `.env` is missing or a default (`docs/RUNBOOK.md`, "Next deploy", step 0); check-in alerts are stopped until it's fixed, so treat it as Scenario 4. Notice only if it lasts more than a few hours.

---

## Known gaps

- **One person.** Nobody else can act if Steven is unreachable. Name a second person with read-only access to the monitoring emails and this document, even if they can only post a notice through Steven's accounts with his prior consent. *Owner decision.*
- **No status page.** Notices go on the site itself, which doesn't help when the site is down. A free external status page would be a third party; decide whether that's acceptable (it would only carry outage notices, never user data).
- **Notification law** is unknown for this kind of data; it's in the counsel questions (`docs/legal/`).
- **Test this plan once:** do a dry run of Scenario 4 with the monitoring in `docs/RUNBOOK.md` (stop the api, confirm someone is paged, restart, confirm the heartbeat recovers) and record the date here.

| Date | Drill | Result |
|---|---|---|
| — | Not yet run | — |
