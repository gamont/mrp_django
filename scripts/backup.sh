#!/usr/bin/env bash
set -euo pipefail

STAMP="${1:-$(date +%Y%m%d_%H%M%S)}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"

DB_FILE="$BACKUP_DIR/mrp_${STAMP}.dump"
META_FILE="$BACKUP_DIR/mrp_${STAMP}.sha256"

: "${POSTGRES_DB:=mrp}"
: "${POSTGRES_USER:=mrp}"

# Uses the project's db container, so pg_dump matches the PostgreSQL server version.
docker compose exec -T db pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom \
  --no-owner \
  --no-acl > "$DB_FILE"

sha256sum "$DB_FILE" > "$META_FILE"
printf 'Backup created: %s\nChecksum: %s\n' "$DB_FILE" "$META_FILE"
