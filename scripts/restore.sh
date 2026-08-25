#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 backups/mrp_YYYYMMDD_HHMMSS.dump" >&2
  exit 2
fi

DUMP="$1"
CHECKSUM="${DUMP%.dump}.sha256"
: "${POSTGRES_DB:=mrp}"
: "${POSTGRES_USER:=mrp}"

[[ -f "$DUMP" ]] || { echo "Backup not found: $DUMP" >&2; exit 2; }
if [[ -f "$CHECKSUM" ]]; then
  sha256sum -c "$CHECKSUM"
fi

# Restore is intentionally explicit and destructive.
read -r -p "This will replace database '$POSTGRES_DB'. Type RESTORE to continue: " ANSWER
[[ "$ANSWER" == "RESTORE" ]] || { echo "Cancelled."; exit 1; }

docker compose exec -T db dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB"
docker compose exec -T db createdb -U "$POSTGRES_USER" "$POSTGRES_DB"
docker compose exec -T db pg_restore \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --no-owner \
  --no-acl < "$DUMP"

docker compose run --rm -e SKIP_DJANGO_BOOTSTRAP=1 web python manage.py migrate --noinput
docker compose run --rm -e SKIP_DJANGO_BOOTSTRAP=1 web python manage.py check
printf 'Restore completed: %s\n' "$DUMP"
