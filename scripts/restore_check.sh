#!/usr/bin/env sh
# Rehearses a restore: decrypts a backup into the THROWAWAY test database and
# reports table row counts. Never touches the live database.
#   scripts/restore_check.sh backup.dump.age ~/path/to/age-identity.txt
set -eu
backup="${1:?usage: restore_check.sh BACKUP.dump.age AGE_IDENTITY_FILE}"
identity="${2:?usage: restore_check.sh BACKUP.dump.age AGE_IDENTITY_FILE}"
cd "$(dirname "$0")/.."
compose="docker compose -p solusvires-test -f docker-compose.test.yml"
$compose up -d --wait db-test
db=$($compose ps -q db-test)
age -d -i "$identity" "$backup" \
  | docker exec -i "$db" pg_restore -U solusvires -d solusvires_test --clean --if-exists --no-owner
docker exec "$db" psql -U solusvires -d solusvires_test -At -c "
  SELECT 'alembic ' || version_num FROM alembic_version
  UNION ALL SELECT 'users ' || count(*) FROM users
  UNION ALL SELECT 'evidence_entries ' || count(*) FROM evidence_entries
  UNION ALL SELECT 'trusted_contacts ' || count(*) FROM trusted_contacts;"
echo "restore OK. Run 'scripts/preview.sh down' to discard the restored copy."
