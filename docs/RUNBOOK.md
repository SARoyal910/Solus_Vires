# Runbook

How to deploy, back up, and restore Solus Vires. Keep this current; the
"last done" dates are the evidence that it works.

## Where things run

- **Production:** a DigitalOcean droplet behind Cloudflare. It runs the
  Docker Compose stack (nginx, api, Postgres) from a git checkout of **`main`**
  and is updated by hand with `git pull`. Visitors reach it only through
  Cloudflare.
- **The owner's Mac:** a local copy of the same stack for development and
  testing. Changing it changes nothing on solusvires.com.
- **Phase 2 work** happens in the `~/Projects/solusvires-phase2` worktree
  (branch `phase2`). Preview with `scripts/preview.sh`
  (http://127.0.0.1:8099, throwaway database). Test with `scripts/test.sh`.

## Deploying

On the Mac:
1. In the worktree: `scripts/test.sh` and `node --test tests/web/` are green.
2. Bring the work into `main` and push:
   `git checkout main && git merge --ff-only phase2 && git push origin main`
   (merge into `dev` too if you keep it as the integration branch).

On the droplet:
3. `cd` to the checkout, `git status` (must be clean), `git pull origin main`.
4. `docker compose up -d --build`. Rebuilds the api (applies migrations on
   start, until P2-A15 makes that a separate step) and recreates nginx if its
   mounts changed.
5. From anywhere: `scripts/probe_headers.sh https://solusvires.com` shows
   every line `ok`. If a change doesn't show, purge Cloudflare's cache
   (Caching > Configuration > Purge Everything) before assuming it failed.
6. Spot-check in a browser: home page, Notes unlock, check-in page.

### First Phase 2 deploy (Sprints 0-1) — extra steps on the droplet

- **Before step 4**, add invite codes to the droplet's `.env`, or new sign-ups
  are paused (existing accounts are unaffected):
  `BETA_SIGNUPS_ENABLED=false` and `BETA_INVITE_CODES=code-1,code-2`
  (one per person you invite).
- **Take a backup first** (see below): migrations 0003 (Notes PIN key-check)
  and 0004 (push endpoints per contact) run when the api starts.
- nginx gains a new mount (`nginx/snippets`); `up -d` recreates it.
- Production `main` was at `752b953` before this deploy, so it also brings in
  the per-IP rate limiting from `e175ccf`.
- Rollback: `git checkout 752b953 -- html nginx docker-compose.yml backend`
  then `docker compose up -d --build`. Migrations 0003/0004 can stay applied;
  the old code ignores them.

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
   `15 3 * * * cd /path/to/solusvires && BACKUP_AGE_RECIPIENT="$(cat ~/solusvires-backup.recipient)" scripts/backup.sh ~/solusvires-backups >> ~/solusvires-backups/backup.log 2>&1`
4. Get copies off the droplet: DigitalOcean's own backups/snapshots of the
   droplet, and/or periodically `scp` the newest `.dump.age` to the Mac.
   The files are encrypted, so storing them anywhere is safe.

Keeps the newest 30 dumps.

## Restore rehearsal

Do this after setup, then every few months:

1. Copy a recent dump from the droplet to the Mac, then
   `scripts/restore_check.sh solusvires-<latest>.dump.age ~/solusvires-backup-key.txt`
2. Confirm the row counts look right and the alembic version matches production.
3. Record it below. (The script discards the restored copy itself.)

| Date | Backup file | Result | By |
|---|---|---|---|
| 2026-09-26 | Mac's local dev database (not production) | Procedure works: restored cleanly, counts identical to the source | Claude, with the owner |
| — | First droplet backup | Not yet rehearsed | — |

## Real restore (production)

On the droplet, only after a rehearsal has worked. Stop the api first so nothing writes:
`docker compose stop api`, then
`age -d -i KEY FILE.dump.age | docker exec -i solusvires_db pg_restore -U solusvires -d solusvires --clean --if-exists --no-owner`,
then `docker compose start api` and run the probe.
