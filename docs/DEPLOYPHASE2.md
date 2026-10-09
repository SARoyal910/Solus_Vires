# Deploy Phase 2: the owner's remaining steps

**Written:** 2026-10-07, after the `investor-ready` work was merged and deployed.
**Who:** the owner. Nothing here can be done from the code; each step needs an account, the droplet console, a phone, or another person.
**Where you are** is marked on every step: **Mac**, **browser**, or **droplet** (the console at `/root/solusvires`).

Done so far today: branch merged, migration 0008 applied, the `alert-worker` container live and healthy, the nginx stale-address 502 understood. Tick each step below as you finish it and put the date in the brackets.

---

## Step 0. Finish today's deploy `[ ]`

**Droplet**, if the smoke test hasn't passed yet:

```
docker compose exec web nginx -s reload
scripts/smoke.sh https://solusvires.com
```

Expect `SMOKE OK`. Confirm the loop moved to the worker:

```
docker compose logs --tail 20 api | grep checkin_alert_loop_disabled
docker compose logs --tail 5 alert-worker
```

The worker log shows `alert_worker_starting` and then nothing. That silence is normal.

**Mac**: push the nginx fix (it is committed on `main`, unpushed):

```
cd ~/Projects/solusvires
git push origin main
```

Wait for CI to go green on `main`, then **droplet** (no containers restart, so no backup or migration):

```
cd /root/solusvires
git pull origin main
docker compose exec web nginx -t && docker compose exec web nginx -s reload
scripts/smoke.sh https://solusvires.com
```

Also set a git identity on the droplet so an emergency commit there never fails again. It never needs to push:

```
git config user.name "solusvires droplet"
git config user.email "droplet@solusvires.local"
```

## Step 1. Monitoring `[ ]`

Half an hour. **Follow `docs/MONITORING_SETUP.md`**, which is this step written out click by click with the exact values; the summary below is the same thing.

**Browser**
1. uptimerobot.com, free plan, sign up with the operator email. New monitor: type Keyword, URL `https://solusvires.com/api/health`, keyword `ok`, alert when the keyword **does not exist**, interval 5 minutes, alert contact your email.
2. healthchecks.io, free plan, same email. Add a check named `alert-loop`: period 5 minutes, grace 10 minutes. Copy its ping URL (`https://hc-ping.com/<uuid>`). Add a second check named `backup-offsite`: period 1 day, grace 2 hours. Copy its URL too; Step 3 uses it.

**Droplet**
3. Add to `.env`:
   ```
   HEALTHCHECK_PING_URL=https://hc-ping.com/<alert-loop uuid>
   ```
   then `docker compose up -d --wait`. Within 5 minutes `alert-loop` turns green.

**Forced test**, at a quiet time:
4. `docker compose stop api alert-worker`. Expect an UptimeRobot email in about 10 minutes and a Healthchecks email in about 15.
5. `docker compose start api alert-worker && docker compose up -d --wait`. Both services send a "back up" email.
6. Record the date in the forced-test table in `docs/RUNBOOK.md` "Monitoring" and in `docs/INCIDENT_PLAN.md` Scenario 4.

## Step 2. Postmark, the second email provider `[ ]`

Twenty minutes. Without it, alerts still stop silently when Brevo's daily cap is reached.

**Browser**
1. postmarkapp.com, sign up with the operator email, create one server. Free tier is 100 emails a month, enough for failover.
2. Sender Signatures: add the same address as `BREVO_SENDER_EMAIL` in your `.env` and click the verification email. (A different verified address works too; then also set `POSTMARK_SENDER_EMAIL=<that address>` below.)
3. Server, API Tokens tab: copy the Server API Token.

**Droplet**
4. Add to `.env`:
   ```
   POSTMARK_SERVER_TOKEN=<token>
   ```
   then `docker compose up -d --wait`.
5. One-off failover test: set `BREVO_API_KEY=wrong` in `.env`, `docker compose up -d --wait`, send yourself a trusted-contact invite from a test account, then
   `docker compose logs --tail 50 api | grep -E "email_provider_failed|email_failed_over"`.
   You should see both lines and receive the email. Put the real Brevo key back and `docker compose up -d --wait`.

## Step 3. Backups off the droplet `[ ]`

Forty minutes. Runbook section "Backups" has the one-time setup in full.

**Browser**
1. DigitalOcean: if the droplet is not already in a project of its own, create a project named Solus Vires and move the droplet into it. Nothing else ever goes in this project (`docs/SCALE.md` §2.4).
2. Droplet page, Backups tab: enable weekly backups.
3. Spaces: create a bucket `solusvires-backups` in the droplet's region, **file listing restricted**. Then API, Spaces Keys: generate a key for it and copy both halves now; the secret is shown once.

**Droplet**
4. Install and configure rclone, then copy once by hand:
   ```
   apt install -y rclone
   rclone config create spaces s3 provider=DigitalOcean access_key_id=<key> secret_access_key=<secret> endpoint=<region>.digitaloceanspaces.com
   OFFSITE_REMOTE=spaces:solusvires-backups scripts/offsite_copy.sh ~/solusvires-backups
   rclone ls spaces:solusvires-backups
   ```
   The last command lists one file.
5. `crontab -e`: replace the backup line with the one in `docs/RUNBOOK.md` "Backups" step 3, with the `backup-offsite` ping URL from Step 1 in `BACKUP_PING_URL`. It runs the dump, then the copy, and pings success or `/fail`.
6. Next morning: the `backup-offsite` check is green and `rclone ls spaces:solusvires-backups` shows two files.

**Keys**: move `~/solusvires-backup-key.txt` off the Mac into the password manager (Step 7) if it is still there. It is the only thing that opens these files.

## Step 4. Restore rehearsal `[ ]`

One hour, after Step 3 has produced a file in the bucket. This gives you a measured recovery time.

**Mac**
1. Configure the same rclone remote on the Mac (`brew install rclone`, same `rclone config create` line as Step 3).
2. Fetch the newest dump and time the restore:
   ```
   cd ~/Projects/solusvires
   rclone copy spaces:solusvires-backups/$(rclone lsf spaces:solusvires-backups | sort | tail -1) .
   time scripts/restore_check.sh solusvires-*.dump.age ~/solusvires-backup-key.txt
   ```
3. Confirm the row counts look right and the alembic version is 0008.
4. Record the date, file and duration in the restore table in `docs/RUNBOOK.md` "Restore rehearsal". Delete the local dump afterwards.

## Step 5. Canary account `[ ]` started, `[ ]` four green weeks

Fifteen minutes to set up, two minutes a week. It is the only check that proves the whole alert path end to end (`docs/SCALE.md` §5.2).

**Browser and phone**
1. Register an account with an invite code. Username something like `canary-ops`.
2. Check-ins page: add your own email as a trusted contact, accept the invite from the email on your phone, enable push there.
3. Set the schedule to a weekly interval with a short grace period.
4. Each week: let it go overdue once. Confirm the numbered alert arrives by email and by push, within 10 minutes of the deadline plus grace. Check in. Confirm the all-clear arrives.
5. Keep a dated log (a row per week: alert time, email yes/no, push yes/no, all-clear yes/no). Four green weeks in a row is what the investor pack wants. A miss is a Sev-1 under `docs/INCIDENT_PLAN.md`.

## Step 6. Load test on droplet-sized hardware `[ ]`

One evening, optional before the pitch but it turns the Mac numbers in `docs/SCALE.md` §2.2 into production-shaped ones.

**Browser**: create a temporary $6 droplet (same size as production) with Docker preinstalled, in the Solus Vires project.
**That droplet**: clone the repo, `pip install httpx` or use the system python with httpx, then
```
PYTHON=python3 scripts/loadtest.sh
```
Copy the JSON into §2.2 under a new dated row, then destroy the droplet.

## Step 7. Second person and the vault `[ ]`

One hour plus a conversation.

1. Pick a password manager with shared vaults. Create a vault named Solus Vires Operations.
2. Put in it: the backup key file, `RECOVERY_CODE_PEPPER`, `CHECKIN_TOKEN_SECRET`, the Brevo and Postmark tokens, the DigitalOcean login and API token, the Spaces key, the Cloudflare login, the Healthchecks and UptimeRobot logins, the droplet root access.
3. Share the vault with one trusted person. Walk them through `docs/INCIDENT_PLAN.md` once: how to reach the console, how to run `docker compose ps`, `docker compose restart api`, and how to reach you.
4. Name them in `docs/INCIDENT_PLAN.md`. Commit and push that from the Mac.
5. Decide the two addresses and set them in `.env` on the droplet, then `docker compose up -d --wait`:
   ```
   CONTACT_INBOX_EMAIL=<public contact address>
   OPERATOR_ALERT_EMAIL=<where operator alerts go>
   ```

## Step 8. Send the review requests `[ ]` legal, `[ ]` advocacy

Start this first; it has the longest tail and gates public sign-ups, the retention policy and the design freeze.

1. The packets are in `docs/legal/` and `docs/advocacy/`. Read each once more and fill in anything dated.
2. Legal: a lawyer with privacy or technology practice, ideally one who has worked with domestic-violence organisations. Bar association referral services and law-school clinics are the cheap routes.
3. Advocacy: a domestic-violence organisation, with at least one reviewer experienced with male survivors. Start with the national coalition in your state; they can refer.
4. Send both. Record the date sent and to whom in `docs/TODO.md`.
5. When replies arrive, the work they unlock is listed in `docs/TODO.md` "Blocked until the reviews come back".

## Step 9. Cloudflare cleanup `[ ]`

Twenty minutes.

1. Workers & Pages: open the `solus-vires` Worker. Check it has no routes on solusvires.com. If none, delete it; otherwise disconnect its repository under Settings, Builds. It is what adds the failing "Workers Builds" check to every pull request.
2. Confirm Rocket Loader, Email Address Obfuscation and Web Analytics are off, and no page rule or cache rule caches HTML (`docs/RUNBOOK.md` "Cloudflare settings the site depends on").
3. Add the cache rule for static assets only: cache `.css`, `.js`, `.png`, `.svg` for an hour; never HTML (`docs/SCALE.md` Stage 0 item 7).

## Step 10. Fill the investor pack `[ ]`

After four green canary weeks (Step 5) and with Steps 1 to 4 done. Open `docs/INVESTOR_PACK.md` and fill the nine `[ ]` blanks from:

- UptimeRobot: uptime percentage, last 30 and 90 days.
- Healthchecks: late or missed pings on `alert-loop` and `backup-offsite`, last 30 days.
- The canary log: weeks green of weeks run.
- The restore table in the runbook: last date and duration.
- The load-test rerun (Step 6), if done.
- GitHub Actions: the commit the main branch is green at.

Then publish it in whatever form the conversation needs.

---

## Order and time

| Step | Time | Depends on |
|---|---|---|
| 0 Finish the deploy | 15 min | nothing, do it now |
| 8 Send the review requests | 1 hour | nothing, do it this week |
| 1 Monitoring | 30 min | nothing |
| 2 Postmark | 20 min | nothing |
| 3 Backups off the droplet | 40 min | Step 1 for the ping URL |
| 4 Restore rehearsal | 1 hour | Step 3 |
| 5 Canary | 15 min, then weekly | Step 1 is useful but not required |
| 7 Second person and vault | 1 hour | nothing |
| 9 Cloudflare cleanup | 20 min | nothing |
| 6 Load test on a droplet | 1 evening | nothing, optional |
| 10 Fill the pack | 1 hour | four weeks of Step 5 |

Steps 0, 1, 2, 3 and 9 fit in one evening. Steps 4, 5 and 7 fit in another. Step 8 should go out before either.
