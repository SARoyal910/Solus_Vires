#!/usr/bin/env sh
# Runs lint + the backend test suite against a throwaway Postgres, in the same
# Python version as production (3.12). Extra args are passed to pytest:
#   scripts/test.sh -k lockout
# SV_TEST_PROJECT names the compose project (default solusvires-test), so
# two checkouts can test at the same time without tearing each other down.
set -eu
cd "$(dirname "$0")/.."
compose="docker compose -p ${SV_TEST_PROJECT:-solusvires-test} -f docker-compose.test.yml"
trap '$compose down -v --remove-orphans >/dev/null 2>&1' EXIT
PYTEST_ARGS="$*" $compose run --rm tests
