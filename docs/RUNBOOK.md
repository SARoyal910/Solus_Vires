# Runbook

How to deploy, back up, restore, and monitor Solus Vires. Keep this current; the
"last done" dates are the evidence that it works.

## Where things run

- **Production:** a DigitalOcean droplet behind Cloudflare. It runs the
  Docker Compose stack (nginx, api, alert-worker, Postgres) from the git checkout of
  **`main`** at **`/root/solusvires`**, updated with `scripts/deploy.sh`.
  Visitors reach it only through Cloudflare.
  Secrets live in `/root/solusvires/.env`, which is not in git.
- **The owner's Mac:** `~/Projects/solusvires`, one checkout, usually on
  `main`, with `phase2` as the working branch for new work. It runs a local
  copy of the same stack for development (with
  `docker-compose.override.yml` copied from the example so the api
  live-reloads; the file is gitignored). Changing it changes nothing on
  solusvires.com. nginx requires Cloudflare's client certificate
  (Authenticated Origin Pulls), so direct `https://localhost` requests to
  that stack are refused; use `scripts/preview.sh` for local viewing
  (http://127.0.0.1:8099, throwaway database). Test with `scripts/test.sh`.
  A second checkout can run its own at the same time:
  `SV_TEST_PROJECT=sv-x scripts/test.sh`,
  `SV_PREVIEW_PROJECT=sv-x-preview PREVIEW_PORT=8130 scripts/preview.sh`.
  (The separate `~/Projects/solusvires-phase2` worktree used during Phase 2
  was removed 2026-10-07.)

## Cloudflare settings the site depends on

- **Web Analytics / Real User Measurements (RUM): Disabled.** When on,
  Cloudflare injects a third-party analytics script into every page,
  including /log.html, which breaks the privacy statement ("no analytics,
  no third-party scripts"). Found and disabled 2026-09-26. Check after any
  Cloudflare change: `curl -s https://solusvires.com/log.html | grep -c cloudflareinsights`
  must print 0.
- **Authenticated Origin Pulls: Global, on.** nginx refuses connections
  without Cloudflare's client certificate.
- **Rocket Loader and Email Address Obfuscation: Off.** Both work by
  injecting scripts into pages. The Content-Security-Policy (below) blocks
  injected scripts, so with either one on, pages would load with errors.
- **No "Cache Everything" rule for HTML.** nginx sends pages as `no-cache`
  (private pages `no-store`) and serves a second copy of every page under
  `/plain/`. Cloudflare must keep passing HTML through, not cache it.

## Content-Security-Policy

Every response carries one `Content-Security-Policy` header, set in
`nginx/snippets/security-headers.conf`: scripts, styles, images, and
connections only from this site, no inline script or style. It is enforced,
not report-only, because there is nowhere to send reports without logging
the pages visitors open.

- Check it: `scripts/probe_headers.sh https://solusvires.com` (also part of
  `scripts/smoke.sh`).
- If a page breaks after a deploy (blank section, a button that does
  nothing; the browser console shows "Refused to ... because it violates
  the Content Security Policy"): in that snippet, rename the header to
  `Content-Security-Policy-Report-Only`, then
  `docker compose exec web nginx -s reload`. Pages work again at once. Fix
  the page, then rename it back.
- New pages and scripts: no inline `<script>`, no `onclick=` style
  attributes, no `style=` attributes. `tests/browser/csp_clickthrough.mjs`
  clicks through every page under the real policy.

## Checks that need a real phone

Automated tests run in desktop Chrome sized like a phone. These still need a
person with a device, once after the next deploy, results noted here:

- Quick Exit on iPhone Safari, Android Chrome, and a desktop browser: the
  current page must be replaced even when the new tab is blocked.
- Notes: "Print or save a copy" to PDF on iPhone and Android.
- Notes: add a photo from the camera roll on iPhone (HEIC) and Android; a
  large photo on an older phone.
- Plain view, and the `/plain/` link with JavaScript off.
- "Save on this device" on Emergency, then open it in airplane mode.
- A real push notification on Android and on an iPhone home-screen app, a
  real Brevo email, and the alert loop firing on its own timer (P2-E6).

## Deploying

Migrations are a separate, explicit step (P2-A15). The api container no
longer runs `alembic upgrade head` when it starts, and production no longer
bind-mounts `backend/app`: it runs exactly the code built into the image.
`scripts/deploy.sh` does the droplet steps in the right order and stops at
the first problem; the manual equivalent is listed under it.

On the Mac:
1. In the worktree: `scripts/test.sh` and `node --test tests/web/` are green.
2. Bring the work into `main` and push:
   `git checkout main && git merge --ff-only phase2 && git push origin main`
   (`dev` is no longer used; `phase2` is the working branch and `main` is
   what the droplet runs).

On the droplet:
3. `cd` to the checkout, `git status` (must be clean), `git pull origin main`.
4. Run the deploy:
   ```
   BACKUP_AGE_RECIPIENT="$(cat ~/solusvires-backup.recipient)" scripts/deploy.sh https://solusvires.com
   ```
   It refuses to run with uncommitted changes or a source bind mount, takes
   an encrypted backup, builds the api image, applies migrations
   (`scripts/migrate.sh`), recreates whatever changed, waits until every
   container is healthy, then runs the smoke test. `SKIP_BACKUP=1` skips the
   backup; only use it when `git log` shows no new file in
   `backend/migrations/versions/`.

   The same thing by hand, in this order:
   ```
   scripts/backup.sh ~/solusvires-backups        # with BACKUP_AGE_RECIPIENT set
   scripts/migrate.sh                            # builds the api image, then alembic upgrade head
   docker compose up -d --wait                   # fails if any container isn't healthy
   scripts/smoke.sh https://solusvires.com       # LAST step, see below
   ```
5. **Last step, every deploy:** `scripts/smoke.sh https://solusvires.com`
   prints `SMOKE OK`. It is read-only (GET requests only) and checks the
   security headers on every page (`scripts/probe_headers.sh`), that
   `/api/health` answers and the API refuses an anonymous `/api/auth/me`,
   that every page and asset in `html/` returns 200, that the private pages
   are `no-store`, and that no third-party script (Cloudflare Web Analytics,
   say) has been injected. It reads the page list from the checkout it runs
   in, so run it from the commit you just deployed (the droplet, or the Mac
   on the same commit). If a change doesn't show, purge Cloudflare's cache
   (Caching > Configuration > Purge Everything) before assuming it failed.
6. Spot-check in a browser: home page, Notes unlock, check-in page.

**If you forget the migrate step:** the api container's healthcheck compares
the database's migration version with the one the code expects. A mismatch
makes it `unhealthy` within about a minute, `docker compose up -d --wait`
exits with an error, and `docker compose ps` shows `(unhealthy)`. The reason
is in `docker inspect --format '{{json .State.Health}}' solusvires_api`
("database schema is [...], this code needs [...]: run scripts/migrate.sh").
The public pages keep working (nginx doesn't wait for the api); fix it with
`scripts/migrate.sh` then `docker compose up -d --wait` (migrate.sh restarts an api that is already running and unhealthy, so the health check is judged again against the migrated database rather than the stale verdict). Note that plain
`docker compose up -d --build` (the old step) returns success without
waiting; that's why the steps above use `--wait`.

**Order matters.** Migrate *before* `up`: for a minute the old api runs on
the new schema, which is fine because migrations here only add things. A
migration that removes or renames something (e.g. 0008, dropping the old
lockout columns) must ship one release after the code stops using it.

**Rolling back:** check out the previous commit and run
`docker compose up -d --build --wait`. Migrations can stay applied, since
older code ignores added columns. One trap: commits from before P2-A15
(`83be254` and earlier) still run `alembic upgrade head` when the api
starts, and fail to start if the database is at a revision they've never
heard of. Rolling back past P2-A15 after a newer migration has run means
downgrading first, with the *new* image still in place:
`docker compose run --rm api alembic downgrade <revision the old code knows>`.

### Next deploy: alert worker, email fallback, off-site backups (migration 0008)

The first deploy of `main` after 2026-10-07 brings SCALE.md Stage 1 items 2
and 5 and Stage 0 item 2. It adds a container, a migration and three optional
settings. `scripts/deploy.sh` handles the build, migration and wait as usual;
these are the parts it can't do for you.

**Before pulling.** Nothing: every new setting is optional and defaults to
the old behaviour, except that the alert loop moves out of the api (below).

**What changes when `deploy.sh` runs:**
- **Migration 0008** adds `checkin_alert_log.emails_via_fallback`
  (additive; old code ignores it). Expect `before: 0007 (head)`,
  `after: 0008 (head)`.
- **A fourth container, `solusvires_alert_worker`**, runs the check-in
  alert loop from the same image (`python -m app.alert_worker`). The api
  no longer runs it: compose now passes `CHECKIN_ALERT_LOOP_ENABLED=false`
  to the api unless `.env` says otherwise. If your `.env` sets
  `CHECKIN_ALERT_LOOP_ENABLED=true`, remove the line (or leave it: both
  loops running is harmless because of the advisory lock, but then a web
  deploy still pauses alerts, which is what this change removes).
  `docker compose ps` should show `alert-worker ... (healthy)`; it is
  unhealthy when no pass has run for three check intervals (15 minutes).
  `docker compose logs --tail 20 alert-worker` shows `alert_worker_starting`
  and then nothing until a pass sends something; that silence is normal.
- **The Healthchecks.io heartbeat now comes from the worker.** Nothing to
  change: the same `HEALTHCHECK_PING_URL` is passed to both containers and
  only the process running the loop pings. The forced test in "Monitoring"
  changes: stopping the api tests UptimeRobot, stopping the alert-worker
  tests Healthchecks.

**After the deploy, when you have time (each is optional and independent):**
1. **Second email provider.** Create a Postmark account (free tier is 100
   emails a month, enough for failover, not for daily use), verify the
   sender address (the same one as `BREVO_SENDER_EMAIL`, or set
   `POSTMARK_SENDER_EMAIL`), and put the server token in `.env` as
   `POSTMARK_SERVER_TOKEN`. Then `docker compose up -d --wait`. From then
   on, when Brevo returns an error or a quota response, the message goes
   out through Postmark instead; the alert history records how many emails
   each alert sent that way (`emails_via_fallback`), and the api log shows
   `email_failed_over`. A run of those lines means Brevo's cap is gone:
   SCALE.md Stage 1 item 1. Test it once by putting a wrong `BREVO_API_KEY`
   in `.env` for one restart and sending yourself a contact invite; the log
   shows `email_provider_failed` for brevo and `email_failed_over` to postmark.
2. **Off-site backup copy.** See "Backups" step 4: `rclone` to a private
   Spaces bucket, chained after the nightly dump, with its own Healthchecks
   check so a copy that stops is noticed.

**What happened on the first deploy (2026-10-07):** every container came up
healthy, then the smoke test got 502 from `/api/health`. nginx had resolved
`api` to an address at its own start eleven days earlier; the new
alert-worker container was handed that address, so nginx was proxying API
calls to a process with no web server. `docker compose exec web nginx -s reload`
fixed it in a second. The proxy snippet now names the upstream through a
variable so nginx re-resolves it (`nginx/snippets/api-proxy.conf`), and
`deploy.sh` reloads nginx after the containers come up. If `/api/` ever 502s
right after a deploy while `docker compose ps` is all healthy, that reload
is the first thing to try.

**And on the Phase 3 deploy (2026-10-07, migrations 0009–0012):** the
alert-worker came up unhealthy because it had its own image build, which
`deploy.sh` never rebuilt; it ran the old code against the new schema. Fixed
by `docker compose build alert-worker && docker compose up -d --wait`, and
for good by having the worker run the api's image (`image: solusvires-api`,
no `build`). If a worker is ever unhealthy right after a deploy with the
api healthy, check `docker compose images` shows both on the same image id.

**Rolling back:** `git checkout` the previous commit and
`docker compose up -d --wait --remove-orphans` (the flag removes the worker
container). Migration 0008 can stay applied; nothing before it reads the
column. If you roll back, set `CHECKIN_ALERT_LOOP_ENABLED=true` in `.env`
first or the old api will not run the loop either, and alerts stop.

### Next deploy: what changes on the droplet (Phase 2 Sprints 2-5)

**Done 2026-10-04** (`main` at `2b81477`): pepper set, database password
rotated, migrations 0004 → 0007, smoke green. Kept for the record; the live
checkout is `/root/solusvires` (an old unused copy at `/srv/solusvires` was deleted 2026-10-07).
From now on a deploy is `scripts/deploy.sh` ("Deploying" above).

This was a one-time change, the first time `main` included P2-A15 and the Lane A hardening
work. It changes how deploys work, adds required secrets, and runs new
migrations.

**0. Before anything else, fix `.env` on the droplet.** In production the
api now **refuses to start** if any of these three is empty, a placeholder
(`replace-with-...`), or a known default (`solusvires`, `postgres`,
`password`, `test-only`, `changeme`, empty). While it refuses, the API is
down: no logins, no notes, and **no check-in alerts** go out until it's
fixed. `scripts/deploy.sh` checks the same thing and stops before building.
- `RECOVERY_CODE_PEPPER` (new, required; compose won't even start without
  it). Generate once:
  `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
  **Never change it after it's set**: every recovery code issued under the
  old value would stop working, with no way to recover them. Keep a copy
  with the backup key (password manager).
- `CHECKIN_TOKEN_SECRET` must be a real random value (same command). If it
  is already set on the droplet, **keep it**: changing it breaks every
  invite and "manage alerts" link already emailed.
- `POSTGRES_PASSWORD` must not be a default. If it is, changing `.env`
  alone is not enough, because Postgres keeps the password it was created
  with: first
  `docker compose exec db psql -U solusvires -d solusvires -c "ALTER USER solusvires PASSWORD 'new-value';"`,
  then put the same value in `.env`.
- Optional, all off when empty: `HEALTHCHECK_PING_URL` (see "Monitoring"),
  `OPERATOR_ALERT_EMAIL` (one email when one address is refused by the rate
  limits more than `ABUSE_ALERT_THRESHOLD`, default 50, times in an hour;
  the email never contains the IP, at most 5 a day),
  `CONTACT_INBOX_EMAIL` and `CONTACT_RESPONSE_DAYS` (default 7; the contact
  form sends to that inbox through Brevo and stores nothing; without an
  inbox, or without `BREVO_API_KEY`, the form says plainly that it's off).
  `CHECKIN_ALERT_LOOP_ENABLED` defaults to on in compose; leave it.

Then:

1. **Before pulling**, check for a local override:
   `ls docker-compose.override.yml`. If it exists and mounts `backend/app`,
   move it out of the checkout (`mv docker-compose.override.yml ~/`).
   `deploy.sh` refuses to run while a source mount is configured.
2. `git pull origin main`.
3. Take a backup: `BACKUP_AGE_RECIPIENT="$(cat ~/solusvires-backup.recipient)" scripts/backup.sh ~/solusvires-backups`.
   This deploy has migrations, so this is not optional.
4. `scripts/migrate.sh`. It prints `before:` and `after:`. Expect
   `before: 0004 (head)` and an `after` ending in `(head)` at the newest
   revision: **0005** (recovery codes stored as a peppered HMAC), **0006**
   (check-in alert history and push health), and **0007** (encrypted
   safety plan and photo attachments). All three only add tables and
   columns.
5. `docker compose up -d --wait`. Expect compose to **recreate all three
   containers once**: the api (new command, no bind mount, healthcheck, new
   settings), the database (it gained a healthcheck; the data lives in the
   `db_data` volume, which is kept, so this is a few seconds' restart), and
   nginx only if its config changed. `docker compose ps` should then show
   `api ... (healthy)` and `db ... (healthy)`. If the api keeps restarting,
   `docker compose logs --tail 20 api` shows a `refusing_to_start:` line
   naming the setting (never its value): back to step 0.
6. Check the source mount is gone:
   `docker inspect --format '{{json .Mounts}}' solusvires_api` prints `[]`.
7. `scripts/smoke.sh https://solusvires.com` prints `SMOKE OK`.
8. Set up monitoring (below) if it isn't yet, and run its forced test.
9. From the following deploy on, use `scripts/deploy.sh` (step 4 above).

**Rolling back after this deploy:** migrations 0005 and 0006 can stay
applied for older code, with one exception: recovery codes created after
this deploy exist only as an HMAC, and code from before 0005 can't check
them (recovery would fail for those accounts). Prefer fixing forward. If
you must go back past it, run
`docker compose run --rm api alembic downgrade 0004` with the new image
first; that deletes the HMAC-only codes (those people keep their password
but need new codes).

If step 5 fails with "unhealthy" and no `refusing_to_start` line, run step 4
again and look at `docker compose logs --tail 50 api`. To undo the deploy,
see "Rolling back" above: don't mix the old `docker-compose.yml` with the new
code (the new api needs `RECOVERY_CODE_PEPPER`, which the old file doesn't pass).

**On the Mac**, the owner's local `.env` also needs `RECOVERY_CODE_PEPPER`
(any value locally) or `docker compose` refuses to start, and the local stack
loses its live-reload source mount the next time it is brought up. To keep editing without rebuilding:
`cp docker-compose.override.example.yml docker-compose.override.yml`
(gitignored). Run `scripts/migrate.sh` after pulling a new migration there
too.

### First Phase 2 deploy (Sprints 0-1), done 2026-09-26

Kept for the record.

- **Before step 4**, add invite codes to the droplet's `.env`, or new sign-ups
  are paused (existing accounts are unaffected):
  `BETA_SIGNUPS_ENABLED=false` and `BETA_INVITE_CODES=code-1,code-2`
  (one per person you invite).
- **Take a backup first** (see below): migrations 0003 (Notes PIN key-check)
  and 0004 (push endpoints per contact) ran when the api started (the
  pre-P2-A15 behaviour).
- nginx gains a new mount (`nginx/snippets`); `up -d` recreates it.
- nginx now requires Cloudflare's origin-pull client certificate (Global
  Authenticated Origin Pulls is on). After step 4, check that a direct
  connection is refused: `curl -sk https://127.0.0.1 -H 'Host: solusvires.com'`
  on the droplet should fail with a 400 "No required SSL certificate", while
  https://solusvires.com still loads. If the site itself errors, remove the
  `authenticated-origin-pulls.conf` include line and `docker compose restart web`.
- Production `main` was at `752b953` before this deploy, so it also brings in
  the per-IP rate limiting from `e175ccf`.
- Rollback: `git checkout 752b953 -- html nginx docker-compose.yml backend`
  then `docker compose up -d --build`. Migrations 0003/0004 can stay applied;
  the old code ignores them.

## Monitoring

Two free services watch the site from outside and email the owner,
**Steven Royal**, when something stops (P2-F2). Neither sees any visitor or
survivor data: one fetches a public health URL, the other only receives an
empty "I'm alive" request from the droplet. Sign-ups are done by the owner;
nothing here has been set up yet.

### 1. Is the site up? UptimeRobot on /api/health

Free plan: 50 monitors, checked every 5 minutes, email alerts, keyword
checks ("good for hobby and non-profit projects", uptimerobot.com/pricing,
checked 2026-10-02).

1. Sign up at uptimerobot.com with the operator email address.
2. Add a monitor: type **Keyword**, URL `https://solusvires.com/api/health`,
   keyword `"ok"`, alert when the keyword **does not exist**, interval
   5 minutes. That catches nginx up but the API down (a 502 page has no
   `"ok"`), not just the droplet being off.
3. Optionally a second **HTTP(s)** monitor on `https://solusvires.com/emergency.html`,
   the page that matters most when everything else is broken.
4. Alert contact: the operator's email. Don't make a public status page
   (it would list the URLs being watched, for no benefit).
5. If Cloudflare's Bot Fight Mode is ever turned on and the monitor starts
   failing while the site works, allow UptimeRobot rather than turning the
   monitor off.

### 2. Are check-in alerts running? Healthchecks.io heartbeat

The alert loop runs in the `alert-worker` container every
`CHECKIN_ALERT_CHECK_SECONDS` (300 s). After each pass that held the alert
lock and finished without an error, it requests `HEALTHCHECK_PING_URL`
(empty means no ping; a failed ping is logged and never affects alerts). If
the pings stop, the loop has stopped, even if `/api/health` still answers,
and Healthchecks.io emails the owner. The container's own healthcheck
(`docker compose ps`) catches the same thing locally, after 15 minutes.
That is the case UptimeRobot can't see. Free "Hobbyist" plan: 20 checks
(healthchecks.io/pricing, checked 2026-10-02).

1. Sign up at healthchecks.io with the operator email address.
2. Add a check named `alert-loop`. **Period: 5 minutes, Grace: 10 minutes**
   (match the period to `CHECKIN_ALERT_CHECK_SECONDS` if you change it).
3. Copy its ping URL (`https://hc-ping.com/<uuid>`). It's a secret in the
   sense that anyone with it can send fake "alive" pings; keep it in `.env`
   only, never in the repo.
4. On the droplet, add to `.env`: `HEALTHCHECK_PING_URL=https://hc-ping.com/<uuid>`,
   then `docker compose up -d --wait` (compose passes it to the api and the alert-worker).
5. Within 5 minutes the check turns green on healthchecks.io.
6. Integrations: email to the operator (on by default).

### 3. Forced test (the P2-F2 / Sprint 5 exit gate)

Do once after setup, then after any change to monitoring, at a quiet time:
1. On the droplet: `docker compose stop api alert-worker`.
2. Expect an UptimeRobot email within about 10 minutes (the api is down),
   and a Healthchecks.io email within about 15 (period + grace; the loop
   is down).
3. `docker compose start api alert-worker`, then `docker compose up -d --wait`.
4. Both send a "back up" email; the healthchecks.io check is green again.
5. Record it below and in `docs/INCIDENT_PLAN.md` (Scenario 4 drill).

| Date | What was tested | UptimeRobot email | Healthchecks email | By |
|---|---|---|---|---|
| — | Not yet set up | — | — | — |

## Backups

Nightly and encrypted. Dumps are encrypted to an **age public key**; the
private key is kept offline (password manager or printed), never on the
droplet, so a compromised server or a leaked backup file reveals nothing.

Backups run **on the droplet**, where the real data is.

One-time setup:
1. On the Mac (done 2026-09-26): `age-keygen -o ~/solusvires-backup-key.txt`.
   Its public key (`age-keygen -y ~/solusvires-backup-key.txt`, starts with
   `age1`) is the only thing the droplet needs. **Then move the key file off
   the Mac** (password manager or USB stick). Losing it loses every backup.
2. On the droplet: `apt install age`, then save the public key to
   `~/solusvires-backup.recipient`.
3. On the droplet, `crontab -e`:
   `15 3 * * * cd /root/solusvires && BACKUP_AGE_RECIPIENT="$(cat ~/solusvires-backup.recipient)" scripts/backup.sh ~/solusvires-backups >> ~/solusvires-backups/backup.log 2>&1 && OFFSITE_REMOTE=spaces:solusvires-backups BACKUP_PING_URL=https://hc-ping.com/<uuid> scripts/offsite_copy.sh ~/solusvires-backups >> ~/solusvires-backups/backup.log 2>&1`
4. Get copies off the droplet, automatically (SCALE.md Stage 0 item 2),
   two ways:
   - Turn on DigitalOcean's weekly droplet backups in the control panel.
     This is the fast path to a whole-server restore.
   - `scripts/offsite_copy.sh` (the second half of the cron line above)
     copies the newest `.dump.age` to a **private** Spaces bucket in the
     Solus Vires DigitalOcean project, checks the copied size, and deletes
     off-site copies older than 30 days, which keeps the privacy page's
     "up to 30 days" true. One-time: `apt install rclone`, create the
     bucket with public listing off, make a Spaces key for it, then
     `rclone config create spaces s3 provider=DigitalOcean access_key_id=... secret_access_key=... endpoint=<region>.digitaloceanspaces.com`.
     Give it a Healthchecks.io check of its own (`backup-offsite`, period
     1 day, grace 2 hours) and put its URL in `BACKUP_PING_URL`: the script
     pings on success and `/fail` on any failure, including a stale dump.
     Run it once by hand and confirm the file appears in the bucket.
   The files are encrypted, so where they land matters less than that they land.

Keeps the newest 30 dumps on the droplet and 30 days of copies in the bucket.

## Restore rehearsal

Do this after setup, then every few months:

1. Copy a recent dump from the droplet to the Mac, then
   `scripts/restore_check.sh solusvires-<latest>.dump.age ~/solusvires-backup-key.txt`
2. Confirm the row counts look right and the alembic version matches production.
3. Record it below. (The script discards the restored copy itself.)

| Date | Backup file | Result | By |
|---|---|---|---|
| 2026-09-26 | Mac's local dev database (not production) | Procedure works: restored cleanly, counts identical to the source | Claude, with the owner |
| 2026-09-26 | `solusvires-20260926T171930Z.dump.age` (droplet, pre-deploy) | Decrypted and restored cleanly; alembic 0002, 0 users (none had signed up on production yet) | Claude, with the owner |

## Real restore (production)

On the droplet, only after a rehearsal has worked. Stop the api first so nothing writes:
`docker compose stop api`, then
`age -d -i KEY FILE.dump.age | docker exec -i solusvires_db pg_restore -U solusvires -d solusvires --clean --if-exists --no-owner`,
then `docker compose start api` and run the probe.

## Working on the droplet for the first time

- **Getting a shell:** `ssh root@<droplet-ip>` from the Mac, or the
  "Console" button on the droplet's page in the DigitalOcean dashboard.
  Then `cd /root/solusvires`; every command in this file runs from there.
- **The web console and pasting:** pasting sometimes drops or changes
  characters, and text copied from a chat or a document can arrive with
  curly quotes (`‘ ’`), which the shell and Postgres reject with a `syntax
  error`. Prefer commands that generate a value on the droplet (for example
  `openssl rand -hex 32`) over pasting one in, and type quotes by hand if a
  pasted command fails oddly.
- **nano:** `nano .env` opens the file. Arrow keys move, typing inserts,
  `Ctrl+O` then `Enter` saves, `Ctrl+X` exits (`Y` if it asks to save).
  There is no mouse.
- **Changing a setting:** edit `.env`, then `docker compose up -d --wait`
  so the api restarts with it. `.env` is read only at container start.
- **Changing the database password:** `.env` alone is not enough, because
  Postgres keeps the password it was created with. Do both in one go:
  `NEWPW=$(openssl rand -hex 32) && docker compose exec db psql -U solusvires -d solusvires -c "ALTER USER solusvires PASSWORD '$NEWPW';" && sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$NEWPW|" .env && grep '^POSTGRES_PASSWORD=' .env`
  then `docker compose up -d --wait` straight away. Done 2026-10-04.
- **Secrets in `.env` to keep in the password manager:** `POSTGRES_PASSWORD`,
  `CHECKIN_TOKEN_SECRET` (changing it breaks every invite link already sent),
  `RECOVERY_CODE_PEPPER` (changing it breaks every recovery code ever issued).
  Never paste their values into a chat, an issue, or a commit.

## Expected console noise

On any page, while signed out, the browser console shows one red line:
`Failed to load resource: the server responded with a status of 401` for
`/api/auth/me`. The page asks whether the visitor is signed in and 401 is
the normal answer when they aren't; the page then shows the signed-out
state. It is not an error. A real problem looks like `Refused to load…` or
`Refused to execute…` naming the Content Security Policy, or a 5xx status.
