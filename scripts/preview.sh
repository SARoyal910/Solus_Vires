#!/usr/bin/env sh
# Serves this checkout at http://127.0.0.1:8099 with a throwaway database.
#   scripts/preview.sh        start (pages update as you edit html/)
#   scripts/preview.sh down   stop and discard the database
set -eu
cd "$(dirname "$0")/.."
compose="docker compose -p solusvires-test -f docker-compose.test.yml"
if [ "${1:-}" = "down" ]; then
  $compose down -v --remove-orphans
  exit 0
fi
$compose up -d preview
printf "waiting for http://127.0.0.1:8099 "
for _ in $(seq 1 90); do
  curl -fs http://127.0.0.1:8099/api/health >/dev/null 2>&1 && { echo " up"; exit 0; }
  printf "."; sleep 1
done
echo " timed out"; $compose logs preview | tail -20; exit 1
