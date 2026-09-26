#!/usr/bin/env sh
# Encrypted backup of the live Postgres. Never writes an unencrypted dump.
#   BACKUP_AGE_RECIPIENT=age1... scripts/backup.sh /path/to/off-host/folder
#
# Encrypts to an age PUBLIC key, so this machine can make backups but cannot
# read them; the matching private key lives offline (see docs/RUNBOOK.md).
# Needs: brew install age
set -eu
dest="${1:?usage: backup.sh DEST_DIR}"
: "${BACKUP_AGE_RECIPIENT:?set BACKUP_AGE_RECIPIENT to your age public key (age1...)}"
command -v age >/dev/null || { echo "age is not installed (brew install age)"; exit 1; }
mkdir -p "$dest"
out="$dest/solusvires-$(date -u +%Y%m%dT%H%M%SZ).dump.age"
docker exec solusvires_db pg_dump -U solusvires -d solusvires -Fc \
  | age -r "$BACKUP_AGE_RECIPIENT" > "$out.partial"
mv "$out.partial" "$out"
echo "wrote $out ($(wc -c < "$out" | tr -d ' ') bytes)"
# Keep the newest 30.
ls -1t "$dest"/solusvires-*.dump.age 2>/dev/null | tail -n +31 | while read -r old; do rm -f "$old"; done
