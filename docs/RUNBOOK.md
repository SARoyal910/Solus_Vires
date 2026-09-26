# Runbook

How to deploy, back up, and restore Solus Vires. Keep this current; the
"last done" dates are the evidence that it works.

## Where things run

- **Origin:** Docker Desktop on the owner's Mac, from the main checkout at
  `~/Projects/solusvires`. Ports 80/443 are published directly; Cloudflare
  proxies the public hostname to it.
- **Bind mounts:** nginx serves `html/`, `nginx/conf.d/`, and `nginx/snippets/`
  straight from that checkout, and the api container mounts `backend/app`.
  **Anything merged into the main checkout is live**: static pages
  immediately, nginx config on reload, API code on restart.
- **Development happens in** the `~/Projects/solusvires-phase2` worktree
  (branch `phase2`). Preview it with `scripts/preview.sh`
  (http://127.0.0.1:8099, throwaway database). Test with `scripts/test.sh`.

## Deploying

1. In the worktree: `scripts/test.sh` and `node --test tests/web/` are green.
2. In the main checkout: `git merge phase2` (or the branch being shipped).
   Static pages are live from this moment, so do step 3 straight away.
3. `docker compose up -d --build`. Rebuilds the api (applies migrations on
   start, until P2-A15 makes that a separate step) and recreates nginx if its
   mounts changed.
4. `scripts/probe_headers.sh https://solusvires.com` — every line `ok`.
5. Spot-check in a browser: home page, Notes unlock, check-in page.

### First Phase 2 deploy (Sprint 1) — extra steps

- **Before step 2**, add invite codes to `.env`, or new sign-ups are paused
  (existing accounts are unaffected):
  `BETA_INVITE_CODES=code-for-person-1,code-for-person-2`
- nginx gains a new mount (`nginx/snippets`), so step 3 must recreate the
  `web` container. `up -d` does this automatically when the compose file changes.
- Migrations 0003 (Notes PIN key-check) and 0004 (push endpoints per contact)
  run when the api container starts.
- Rollback: `git checkout <previous commit> -- html nginx docker-compose.yml backend`
  then `docker compose up -d --build`. Migrations 0003/0004 have working
  downgrades but leaving them applied is harmless to the old code.

## Backups

Nightly, encrypted, off the machine. Dumps are encrypted to an **age public
key**; the private key is kept offline (password manager or printed), never
on this Mac, so a stolen laptop or backup drive reveals nothing.

One-time setup:
1. `brew install age`
2. `age-keygen -o solusvires-backup-key.txt` — note the `public key: age1...`
   line, then move this file **off the machine** (password manager, USB
   stick in a drawer). Losing it means losing every backup.
3. Pick an off-host destination folder (e.g. a synced cloud drive folder or
   an external disk).
4. Cron it (`crontab -e`):
   `15 3 * * * cd ~/Projects/solusvires && BACKUP_AGE_RECIPIENT=age1... scripts/backup.sh "/path/to/offsite" >> ~/solusvires-backup.log 2>&1`

Keeps the newest 30 dumps.

## Restore rehearsal

Do this after setup, then every few months:

1. `scripts/restore_check.sh /path/to/offsite/solusvires-<latest>.dump.age /path/to/solusvires-backup-key.txt`
2. Confirm the row counts look right and the alembic version matches production.
3. `scripts/preview.sh down` to discard the restored copy.
4. Record it below.

| Date | Backup file | Result | By |
|---|---|---|---|
| — | — | Not yet rehearsed | — |

## Real restore (production)

Only after a rehearsal has worked. Stop the api first so nothing writes:
`docker compose stop api`, then
`age -d -i KEY FILE.dump.age | docker exec -i solusvires_db pg_restore -U solusvires -d solusvires --clean --if-exists --no-owner`,
then `docker compose start api` and run the probe.
