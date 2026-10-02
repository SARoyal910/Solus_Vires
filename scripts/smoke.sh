#!/usr/bin/env sh
# shellcheck disable=SC2086  # $curl_opts is a list of flags, split on purpose
# Post-deploy smoke test (P2-B7). The LAST step of every deploy.
#   scripts/smoke.sh https://solusvires.com
#   PROBE_INSECURE=1 scripts/smoke.sh https://127.0.0.1:8443   (self-signed cert)
#
# Read-only: GET requests only, no accounts, no form posts. Checks:
#   1. security headers on every page (scripts/probe_headers.sh)
#   2. /api/health answers {"status":"ok"} and the API rejects an anonymous
#      /api/auth/me (so nginx really reaches the app)
#   3. every page and asset in this checkout's html/ returns 200
#   4. private pages are no-store, so they never sit in a browser cache
#   5. no third-party script crept in (Cloudflare Web Analytics, etc.)
# Pages come from THIS checkout, so run it from the commit you just deployed.
# Exits non-zero on any failure.
set -u
base="${1:?usage: smoke.sh BASE_URL}"
base="${base%/}"
cd "$(dirname "$0")/.." || exit 1
curl_opts="-s --max-time 20"
[ "${PROBE_INSECURE:-0}" = "1" ] && curl_opts="$curl_opts -k"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0
fail() { echo "FAIL $*"; failures=$((failures + 1)); }

echo "== 1. security headers"
scripts/probe_headers.sh "$base" || failures=$((failures + 1))

echo "== 2. API"
code=$(curl $curl_opts -o "$tmp/health" -w '%{http_code}' "$base/api/health")
if [ "$code" = "200" ] && tr -d ' \n' < "$tmp/health" | grep -q '"status":"ok"'; then
  echo "ok   /api/health"
else
  fail "/api/health returned $code: $(head -c 200 "$tmp/health")"
fi
code=$(curl $curl_opts -o /dev/null -w '%{http_code}' "$base/api/auth/me")
if [ "$code" = "401" ]; then
  echo "ok   /api/auth/me refuses anonymous (401)"
else
  fail "/api/auth/me returned $code, expected 401"
fi

echo "== 3. every page and asset returns 200"
paths="/ /es/ $(cd html && find . -type f \( -name '*.html' -o -name '*.js' -o -name '*.css' -o -name '*.json' -o -name '*.png' -o -name '*.svg' -o -name '*.txt' \) | sed 's|^\.||' | sort)"
count=0
for path in $paths; do
  code=$(curl $curl_opts -o /dev/null -w '%{http_code}' "$base$path")
  count=$((count + 1))
  [ "$code" = "200" ] || fail "$path returned $code"
done
echo "checked $count paths"

echo "== 4. private pages are never cached"
for path in /account.html /log.html /checkin.html /checkin-invite.html; do
  curl $curl_opts -o /dev/null -D "$tmp/h" "$base$path"
  if tr '[:upper:]' '[:lower:]' < "$tmp/h" | grep -q '^cache-control:.*no-store'; then
    echo "ok   $path no-store"
  else
    fail "$path is missing Cache-Control: no-store"
  fi
done

echo "== 5. no third-party scripts"
for path in $(echo "$paths" | tr ' ' '\n' | grep -E '(/|\.html)$'); do
  curl $curl_opts -o "$tmp/page" "$base$path"
  if grep -qi 'cloudflareinsights' "$tmp/page"; then
    fail "$path has Cloudflare Web Analytics injected (turn it off: docs/RUNBOOK.md)"
  elif grep -qiE '<script[^>]+src="(https?:)?//' "$tmp/page"; then
    fail "$path loads a script from another origin: $(grep -oiE '<script[^>]+src="(https?:)?//[^"]*' "$tmp/page" | head -1)"
  fi
done
echo "checked the HTML pages"

if [ "$failures" -eq 0 ]; then
  echo "SMOKE OK: $base"
else
  echo "SMOKE FAILED: $failures problem(s) at $base"
  exit 1
fi
