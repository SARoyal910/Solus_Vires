#!/usr/bin/env sh
# Runs lint + the backend test suite against a throwaway Postgres, in the same
# Python version as production (3.12). Extra args are passed to pytest:
#   scripts/test.sh -k lockout
set -eu
cd "$(dirname "$0")/.."
compose="docker compose -p solusvires-test -f docker-compose.test.yml"
trap '$compose down -v --remove-orphans >/dev/null 2>&1' EXIT
PYTEST_ARGS="$*" $compose run --rm tests
