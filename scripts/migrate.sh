#!/usr/bin/env sh
# Applies database migrations: an explicit deploy step, never done on
# container start (engineering review M8, P2-A15). Run it from the checkout,
# after `git pull` and before `docker compose up -d --wait`:
#   scripts/migrate.sh
#
# It builds the api image from this checkout first, so the migrations applied
# are exactly the ones the new code expects, then runs `alembic upgrade head`
# in a one-off container against the stack's own database. Safe to re-run:
# when there is nothing to apply it changes nothing.
#
# Uses whatever stack `docker compose` points at in this directory (honours
# COMPOSE_PROJECT_NAME / COMPOSE_FILE, which is how CI and local tests aim it
# at a throwaway stack). Take a backup first if a migration is pending
# (docs/RUNBOOK.md).
set -eu
cd "$(dirname "$0")/.."

echo "== building the api image from this checkout"
docker compose build api

echo "== migrating (starts the database if it isn't running)"
docker compose run --rm --no-TTY api sh -c '
  set -e
  before=$(alembic current 2>/dev/null | tail -n 1)
  echo "before: ${before:-empty database}"
  alembic upgrade head
  after=$(alembic current 2>/dev/null | tail -n 1)
  echo "after:  $after"
  case "$after" in
    *"(head)"*) ;;
    *) echo "migrate: the database is not at the newest migration" >&2; exit 1 ;;
  esac
'
# If the api or the alert-worker is already running from before these
# migrations (for example a deploy that forgot this step, failed `up --wait`,
# and is now being fixed, or CI's deliberate unmigrated start), its health
# check has already recorded "unhealthy" against the old schema, and
# `up -d --wait` would read that stale verdict and fail at once. Restart it
# so the check starts fresh against the migrated database.
for service in api alert-worker; do
  id=$(docker compose ps -q "$service" 2>/dev/null || true)
  [ -n "$id" ] || continue
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$id" 2>/dev/null || true)
  if [ "$health" = "unhealthy" ]; then
    echo "== the running $service started before these migrations; restarting it so its health check runs again"
    docker compose restart "$service"
  fi
done
echo "== migrations done. Next: docker compose up -d --wait"
