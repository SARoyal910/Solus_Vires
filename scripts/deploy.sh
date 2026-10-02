#!/usr/bin/env sh
# The droplet deploy, in order, stopping at the first problem. Run it on the
# droplet from the checkout, AFTER `git pull origin main` (docs/RUNBOOK.md):
#   BACKUP_AGE_RECIPIENT="$(cat ~/solusvires-backup.recipient)" scripts/deploy.sh https://solusvires.com
#
# 1. refuses to run with uncommitted changes, a missing or default secret in
#    .env, or a source bind mount
# 2. takes an encrypted backup (scripts/backup.sh); SKIP_BACKUP=1 skips it,
#    only for a deploy you know has no migration
# 3. builds the api image and applies migrations (scripts/migrate.sh)
# 4. recreates whatever changed and waits until every container is healthy;
#    the api is only healthy when its schema matches the code
# 5. runs the smoke test against the URL you pass (scripts/smoke.sh)
set -eu
base="${1:?usage: deploy.sh BASE_URL   (e.g. https://solusvires.com)}"
cd "$(dirname "$0")/.."

echo "== 1. preflight"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "deploy: the checkout has uncommitted changes; commit or discard them first" >&2
  exit 1
fi
if ! config=$(docker compose config 2>&1); then
  echo "deploy: docker compose can't read its configuration:" >&2
  printf '%s\n' "$config" | tail -3 >&2
  exit 1
fi
# In production the api refuses to start (and check-in alerts stop) if any of
# these is empty, a placeholder, or a known default. Catch it before building.
for var in CHECKIN_TOKEN_SECRET RECOVERY_CODE_PEPPER POSTGRES_PASSWORD; do
  value=$(printf '%s\n' "$config" | sed -n "s/^ *$var: *//p" | head -n 1 | tr -d '"')
  case "$value" in
    ""|replace-with*|solusvires|postgres|password|test-only|changeme)
      echo "deploy: $var in .env is empty, a placeholder, or a default (docs/RUNBOOK.md)." >&2
      exit 1 ;;
  esac
done
if printf '%s\n' "$config" | grep -q 'target: /backend/app$'; then
  echo "deploy: a source bind mount is configured (docker-compose.override.yml?)." >&2
  echo "        Production must run the built image. Remove it and re-run." >&2
  exit 1
fi
echo "deploying $(git log -1 --format='%h %s')"

echo "== 2. backup"
if [ "${SKIP_BACKUP:-0}" = "1" ]; then
  echo "skipped (SKIP_BACKUP=1)"
else
  : "${BACKUP_AGE_RECIPIENT:?set BACKUP_AGE_RECIPIENT (see docs/RUNBOOK.md), or SKIP_BACKUP=1 when no migration is pending}"
  scripts/backup.sh "${BACKUP_DIR:-$HOME/solusvires-backups}"
fi

echo "== 3. build + migrate"
scripts/migrate.sh

echo "== 4. start and wait for healthy containers"
if ! docker compose up -d --wait --wait-timeout 180; then
  echo "deploy: a container did not become healthy. Look at:" >&2
  echo "  docker compose ps" >&2
  echo "  docker compose logs --tail 50 api" >&2
  exit 1
fi
docker compose ps

echo "== 5. smoke test"
scripts/smoke.sh "$base"
echo "deploy finished: $(git log -1 --format='%h')"
