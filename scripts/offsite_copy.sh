#!/usr/bin/env sh
# Copies the newest encrypted backup off the droplet (SCALE.md Stage 0 item 2)
# and prunes off-site copies older than 30 days, which is what the privacy
# page promises ("kept for up to 30 days"). Runs on the droplet after
# scripts/backup.sh, from the same cron line (docs/RUNBOOK.md "Backups").
#
#   OFFSITE_REMOTE=spaces:solusvires-backups scripts/offsite_copy.sh ~/solusvires-backups
#
# Needs rclone (apt install rclone) with a remote configured for a PRIVATE
# bucket in the Solus Vires DigitalOcean project (SCALE.md §2.4), e.g.
#   rclone config create spaces s3 provider=DigitalOcean \
#     access_key_id=... secret_access_key=... endpoint=nyc3.digitaloceanspaces.com
# The files are age-encrypted, so the bucket holds nothing readable; it is
# the availability copy, not the confidentiality boundary.
#
# Optional: BACKUP_PING_URL (a Healthchecks.io check of its own, daily period).
# Pinged on success; "<url>/fail" on any failure, so a copy that silently
# stops working pages someone instead of being found at restore time.
set -u
src="${1:?usage: offsite_copy.sh BACKUP_DIR}"
: "${OFFSITE_REMOTE:?set OFFSITE_REMOTE to an rclone destination (remote:bucket[/path])}"
ping="${BACKUP_PING_URL:-}"

fail() {
  echo "offsite_copy: $1" >&2
  [ -n "$ping" ] && curl -fsS -m 10 --retry 3 -o /dev/null "$ping/fail" || true
  exit 1
}

command -v rclone >/dev/null || fail "rclone is not installed (apt install rclone)"
newest=$(ls -1t "$src"/solusvires-*.dump.age 2>/dev/null | head -n 1)
[ -n "$newest" ] || fail "no backups in $src"
# Refuse to copy a stale backup: if backup.sh has stopped producing new dumps,
# this must not keep reporting success.
if [ -n "$(find "$newest" -mmin +1500)" ]; then
  fail "newest backup $(basename "$newest") is more than 25 hours old"
fi

rclone copyto "$newest" "$OFFSITE_REMOTE/$(basename "$newest")" --s3-no-check-bucket 2>&1 \
  || fail "copy to $OFFSITE_REMOTE failed"
# The copy must be whole: compare sizes, not just the exit code.
local_size=$(wc -c < "$newest" | tr -d ' ')
remote_size=$(rclone size --json "$OFFSITE_REMOTE/$(basename "$newest")" 2>/dev/null | sed -n 's/.*"bytes":\([0-9]*\).*/\1/p')
[ "$local_size" = "$remote_size" ] || fail "size mismatch after copy (local $local_size, remote ${remote_size:-?})"

# Privacy page: backups are kept for up to 30 days, off-site copies included.
rclone delete "$OFFSITE_REMOTE" --min-age 30d --include 'solusvires-*.dump.age' 2>&1 \
  || fail "pruning copies older than 30 days failed"

echo "offsite_copy: $(basename "$newest") ($local_size bytes) is in $OFFSITE_REMOTE"
[ -n "$ping" ] && curl -fsS -m 10 --retry 3 -o /dev/null "$ping" || true
exit 0
