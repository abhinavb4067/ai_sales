#!/usr/bin/env bash
# Dumps the production database to a timestamped, gzip-compressed file.
# Intended to run on a schedule (cron/systemd timer) against the
# production host or from a container with network access to Postgres —
# this script does not touch application code or Django settings, only
# pg_dump, so it has no Python/venv dependency.
#
# Usage: PGPASSWORD=... ./backup_postgres.sh [output_dir]
set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-ai_sales}"
POSTGRES_DATABASE="${POSTGRES_DATABASE:-ai_sales}"
OUTPUT_DIR="${1:-./backups}"

if [ -z "${PGPASSWORD:-}" ]; then
  echo "PGPASSWORD must be set in the environment." >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_FILE="$OUTPUT_DIR/${POSTGRES_DATABASE}_${TIMESTAMP}.sql.gz"

# -Fc (custom format) would need pg_restore instead of psql to restore;
# plain SQL (-Fp, the default) keeps restore_postgres.sh's `psql < file`
# approach working, at the cost of a slightly larger dump file.
pg_dump \
  --host="$POSTGRES_HOST" \
  --port="$POSTGRES_PORT" \
  --username="$POSTGRES_USER" \
  --no-password \
  "$POSTGRES_DATABASE" | gzip > "$OUTPUT_FILE"

echo "Backup written to $OUTPUT_FILE"

# Retention: keep the last 14 daily backups in this directory, delete
# anything older. Point this script's OUTPUT_DIR at object storage
# (synced separately) for off-host durability — this alone only
# protects against bad migrations/data mistakes, not host loss.
find "$OUTPUT_DIR" -name "${POSTGRES_DATABASE}_*.sql.gz" -mtime +14 -delete
