#!/usr/bin/env bash
# Restores a backup produced by backup_postgres.sh into POSTGRES_DATABASE.
# DESTRUCTIVE: this replaces the current contents of the target database.
# Always restore into a fresh/throwaway database first and verify before
# pointing this at anything a live app is using.
#
# Usage: PGPASSWORD=... ./restore_postgres.sh path/to/backup.sql.gz
set -euo pipefail

BACKUP_FILE="${1:-}"
POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-ai_sales}"
POSTGRES_DATABASE="${POSTGRES_DATABASE:-ai_sales}"

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
  echo "Usage: PGPASSWORD=... $0 path/to/backup.sql.gz" >&2
  exit 1
fi

if [ -z "${PGPASSWORD:-}" ]; then
  echo "PGPASSWORD must be set in the environment." >&2
  exit 1
fi

read -r -p "This will OVERWRITE database '$POSTGRES_DATABASE' on $POSTGRES_HOST. Type the database name to confirm: " CONFIRM
if [ "$CONFIRM" != "$POSTGRES_DATABASE" ]; then
  echo "Confirmation did not match. Aborting." >&2
  exit 1
fi

gunzip -c "$BACKUP_FILE" | psql \
  --host="$POSTGRES_HOST" \
  --port="$POSTGRES_PORT" \
  --username="$POSTGRES_USER" \
  --no-password \
  "$POSTGRES_DATABASE"

echo "Restore complete. Run 'python manage.py migrate' next to apply any migrations newer than this backup."
