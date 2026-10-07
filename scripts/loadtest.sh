#!/usr/bin/env sh
# The one load test SCALE.md Stage 0 item 4 asks for, from the Mac against a
# throwaway stack, never production:
#   - N concurrent public page loads (default 500)
#   - N concurrent logins (default 50), each from its own simulated address
#   - one alert pass with N due schedules (default 1000), email and push stubbed
# Starts its own compose project on PREVIEW_PORT (default 8140), seeds it,
# measures, prints JSON, and tears everything down. Record the numbers in
# docs/SCALE.md §2.2.
#   scripts/loadtest.sh                   defaults
#   LOAD_SCHEDULES=2000 LOAD_LOGINS=100 LOAD_PAGES=1000 scripts/loadtest.sh
#   LOAD_EMAIL_LATENCY_MS=300 scripts/loadtest.sh   model a real email round trip
# Needs Docker and python3 with httpx on the Mac (the repo's .venv has it:
#   PYTHON=.venv/bin/python scripts/loadtest.sh).
set -eu
cd "$(dirname "$0")/.."
project="${SV_LOAD_PROJECT:-solusvires-load}"
export PREVIEW_PORT="${PREVIEW_PORT:-8140}"
compose="docker compose -p $project -f docker-compose.test.yml -f docker-compose.load.yml"
python="${PYTHON:-python3}"
schedules="${LOAD_SCHEDULES:-1000}"
logins="${LOAD_LOGINS:-50}"
pages="${LOAD_PAGES:-500}"
trap '$compose down -v --remove-orphans >/dev/null 2>&1' EXIT

echo "== starting throwaway stack on :$PREVIEW_PORT"
$compose up -d preview >/dev/null
for _ in $(seq 1 120); do
  curl -fs "http://127.0.0.1:$PREVIEW_PORT/api/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -fs "http://127.0.0.1:$PREVIEW_PORT/api/health" >/dev/null || { $compose logs preview | tail -20; exit 1; }

echo "== seeding $schedules overdue schedules and $logins login accounts"
$compose exec -T preview python -m scripts.load_seed "$schedules" "$logins"

echo "== http: $pages concurrent page loads, $logins concurrent logins"
"$python" scripts/loadtest.py "http://127.0.0.1:$PREVIEW_PORT" --logins "$logins" --pages "$pages"

echo "== alert pass over $schedules due schedules (email latency ${LOAD_EMAIL_LATENCY_MS:-0} ms)"
$compose exec -T -e "LOAD_EMAIL_LATENCY_MS=${LOAD_EMAIL_LATENCY_MS:-0}" preview python -m scripts.load_alert_pass
echo "== done (stack discarded)"
