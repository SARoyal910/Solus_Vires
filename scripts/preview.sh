#!/usr/bin/env sh
# Serves this checkout at http://127.0.0.1:8099 with a throwaway database.
#   scripts/preview.sh        start (pages update as you edit html/)
#   scripts/preview.sh down   stop and discard the database
# For a second checkout at the same time, pick another project and port:
#   SV_PREVIEW_PROJECT=sv-other PREVIEW_PORT=8130 scripts/preview.sh
set -eu
cd "$(dirname "$0")/.."
compose="docker compose -p ${SV_PREVIEW_PROJECT:-solusvires-preview} -f docker-compose.test.yml"
if [ "${1:-}" = "down" ]; then
  $compose down -v --remove-orphans
  exit 0
fi
$compose up -d preview
port="${PREVIEW_PORT:-8099}"
printf "waiting for http://127.0.0.1:%s " "$port"
for _ in $(seq 1 90); do
  curl -fs "http://127.0.0.1:$port/api/health" >/dev/null 2>&1 && { echo " up"; exit 0; }
  printf "."; sleep 1
done
echo " timed out"; $compose logs preview | tail -20; exit 1
