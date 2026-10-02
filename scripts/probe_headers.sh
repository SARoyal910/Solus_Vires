#!/usr/bin/env sh
# Asserts that every page and the API carry the security headers.
#   scripts/probe_headers.sh https://solusvires.com
#   PROBE_INSECURE=1 scripts/probe_headers.sh https://localhost   (self-signed cert)
# Exits non-zero if any header is missing anywhere.
set -u
base="${1:?usage: probe_headers.sh BASE_URL}"
curl_opts="-s -o /dev/null -D -"
[ "${PROBE_INSECURE:-0}" = "1" ] && curl_opts="$curl_opts -k"

paths="/ /index.html /is-this-abuse.html /for-men.html /help-someone.html /if-you-get-an-alert.html /es/ /es/emergencia.html /about.html /privacy.html /emergency.html /resources.html /safety.html /legal.html /recovery.html
/contact.html /account.html /log.html /checkin.html /checkin-invite.html /api/health
/plain/ /plain/safety.html /plain/log.html /plain/es/"
required="x-frame-options x-content-type-options referrer-policy x-robots-tag strict-transport-security content-security-policy"
# The CSP must also say the right things, not just exist (P2-A4).
csp_must="default-src 'self' script-src 'self' style-src 'self' object-src 'none' frame-ancestors 'none' base-uri 'none'"

failures=0
for path in $paths; do
  headers=$(curl $curl_opts "$base$path" | tr 'A-Z' 'a-z')
  missing=""
  for h in $required; do
    printf '%s\n' "$headers" | grep -q "^$h:" || missing="$missing $h"
  done
  csp=$(printf '%s\n' "$headers" | grep "^content-security-policy:")
  if [ -n "$csp" ]; then
    [ "$(printf '%s\n' "$csp" | wc -l)" -eq 1 ] || missing="$missing csp(sent-twice)"
    # Split the expectations on directive boundaries: "script-src 'self'" etc.
    rest="$csp_must"
    while [ -n "$rest" ]; do
      directive="${rest%% \'*}"; rest="${rest#* }"; value="${rest%% *}"
      case "$rest" in *" "*) rest="${rest#* }" ;; *) rest="" ;; esac
      printf '%s' "$csp" | grep -q "$directive $value" || missing="$missing csp($directive)"
    done
    case "$csp" in *unsafe-inline*|*unsafe-eval*|*"*"*) missing="$missing csp(unsafe)" ;; esac
  fi
  if [ -n "$missing" ]; then
    echo "FAIL $path missing:$missing"
    failures=$((failures + 1))
  else
    echo "ok   $path"
  fi
done

[ "$failures" -eq 0 ] || { echo "$failures path(s) missing security headers"; exit 1; }
