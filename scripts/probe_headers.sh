#!/usr/bin/env sh
# Asserts that every page and the API carry the security headers.
#   scripts/probe_headers.sh https://solusvires.com
#   PROBE_INSECURE=1 scripts/probe_headers.sh https://localhost   (self-signed cert)
# Exits non-zero if any header is missing anywhere.
set -u
base="${1:?usage: probe_headers.sh BASE_URL}"
curl_opts="-s -o /dev/null -D -"
[ "${PROBE_INSECURE:-0}" = "1" ] && curl_opts="$curl_opts -k"

paths="/ /index.html /emergency.html /resources.html /safety.html /legal.html /recovery.html
/contact.html /account.html /log.html /checkin.html /checkin-invite.html /api/health"
required="x-frame-options x-content-type-options referrer-policy x-robots-tag strict-transport-security"

failures=0
for path in $paths; do
  headers=$(curl $curl_opts "$base$path" | tr 'A-Z' 'a-z')
  missing=""
  for h in $required; do
    printf '%s\n' "$headers" | grep -q "^$h:" || missing="$missing $h"
  done
  if [ -n "$missing" ]; then
    echo "FAIL $path missing:$missing"
    failures=$((failures + 1))
  else
    echo "ok   $path"
  fi
done

[ "$failures" -eq 0 ] || { echo "$failures path(s) missing security headers"; exit 1; }
