#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="$(tr -d '\r\n' < VERSION)"
RELEASE_KEEP_STACK="${RELEASE_KEEP_STACK:-0}"
RELEASE_KEEP_VOLUMES="${RELEASE_KEEP_VOLUMES:-0}"
# Release validation must not reuse or tear down the developer/production compose project.
# A dedicated project gives it its own network, containers and named volumes.
export COMPOSE_PROJECT_NAME="${RELEASE_COMPOSE_PROJECT:-mrp_release_${VERSION//./_}}"
# Host publishing is not used by the gate (checks run inside containers). Port 0 asks
# Docker to allocate an ephemeral host port and avoids conflicts with a running dev stack.
export POSTGRES_HOST_PORT="${RELEASE_POSTGRES_HOST_PORT:-0}"
export WEB_HOST_PORT="${RELEASE_WEB_HOST_PORT:-0}"
# Security deployment checks must be exercised with production-like Django settings,
# independently from the HTTP smoke stack (which stays plain HTTP inside Compose).
# The value is release-gate-only and may be overridden by CI/ops.
export RELEASE_DJANGO_SECRET_KEY="${RELEASE_DJANGO_SECRET_KEY:-mrp-release-gate-1.0.x-7R9wqK4pN8yV2cM6sT3hF5jL1zX0bD9eG4uA6iO8}"

wait_for() {
  local label="$1"; shift
  local attempts="${RELEASE_WAIT_ATTEMPTS:-30}"
  local delay="${RELEASE_WAIT_DELAY_SECONDS:-2}"
  local i
  for ((i=1; i<=attempts; i++)); do
    if "$@"; then
      echo "[OK] $label"
      return 0
    fi
    echo "[WAIT] $label ($i/$attempts)" >&2
    sleep "$delay"
  done
  echo "[FAIL] timeout aguardando $label" >&2
  return 1
}

release_diagnostics() {
  echo '==> Release diagnostics' >&2
  docker compose ps >&2 || true
  for service in db redis web worker beat; do
    echo "--- logs: $service ---" >&2
    docker compose logs --no-color --tail="${RELEASE_LOG_TAIL:-120}" "$service" >&2 || true
  done
}

release_cleanup() {
  local rc="$?"
  trap - EXIT INT TERM
  if (( rc != 0 )); then
    release_diagnostics
  fi
  if [[ "$RELEASE_KEEP_STACK" != "1" ]]; then
    echo '==> Cleanup isolated release stack' >&2
    if [[ "$RELEASE_KEEP_VOLUMES" == "1" ]]; then
      docker compose down --remove-orphans >/dev/null 2>&1 || true
    else
      docker compose down --remove-orphans --volumes >/dev/null 2>&1 || true
    fi
  else
    echo '[INFO] RELEASE_KEEP_STACK=1: containers mantidos para diagnóstico.' >&2
  fi
  exit "$rc"
}
trap release_cleanup EXIT INT TERM

run_web() {
  # One-off release commands must bypass the container bootstrap entrypoint.
  # Otherwise every migrate/check/test command would implicitly run check, migrate,
  # bootstrap_roles and collectstatic before executing the requested command.
  docker compose run --rm -e SKIP_DJANGO_BOOTSTRAP=1 web "$@"
}

run_web_secure() {
  # ``check --deploy`` is meaningless when it merely inherits the development .env
  # (DEBUG=1, insecure cookies, no HSTS). Run a dedicated production-profile check
  # while keeping the later smoke web service on internal plain HTTP.
  docker compose run --rm \
    -e SKIP_DJANGO_BOOTSTRAP=1 \
    -e DJANGO_DEBUG=0 \
    -e DJANGO_SECRET_KEY="$RELEASE_DJANGO_SECRET_KEY" \
    -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,web \
    -e DJANGO_TRUST_PROXY=1 \
    -e DJANGO_SECURE_SSL_REDIRECT=1 \
    -e DJANGO_SESSION_COOKIE_SECURE=1 \
    -e DJANGO_CSRF_COOKIE_SECURE=1 \
    -e DJANGO_SECURE_HSTS_SECONDS=31536000 \
    -e DJANGO_SECURE_HSTS_PRELOAD=1 \
    web "$@"
}

echo "[INFO] release compose project: $COMPOSE_PROJECT_NAME"
echo "[INFO] release host ports: postgres=$POSTGRES_HOST_PORT web=$WEB_HOST_PORT"
./scripts/preflight.sh

echo '==> Build'
docker compose build

echo '==> Start database/redis'
docker compose up -d db redis
wait_for 'PostgreSQL healthy' docker compose exec -T db pg_isready -U "${POSTGRES_USER:-mrp}" -d "${POSTGRES_DB:-mrp}"
wait_for 'Redis healthy' docker compose exec -T redis redis-cli ping

echo '==> PostgreSQL persistence probe'
PROBE_TOKEN="release-${VERSION}-$(date +%s)-$$"
docker compose exec -T db psql -v ON_ERROR_STOP=1 \
  -U "${POSTGRES_USER:-mrp}" -d "${POSTGRES_DB:-mrp}" \
  -c 'CREATE TABLE IF NOT EXISTS release_volume_probe (token text PRIMARY KEY);' >/dev/null
docker compose exec -T db psql -v ON_ERROR_STOP=1 \
  -U "${POSTGRES_USER:-mrp}" -d "${POSTGRES_DB:-mrp}" \
  -c "INSERT INTO release_volume_probe(token) VALUES ('$PROBE_TOKEN');" >/dev/null
# Recreate the database container, not merely restart it. The row must survive through
# the named volume or the release is not safe for production persistence.
docker compose rm -sf db >/dev/null
docker compose up -d db
wait_for 'PostgreSQL healthy after container recreation' docker compose exec -T db pg_isready -U "${POSTGRES_USER:-mrp}" -d "${POSTGRES_DB:-mrp}"
PROBE_FOUND="$(docker compose exec -T db psql -At -v ON_ERROR_STOP=1 \
  -U "${POSTGRES_USER:-mrp}" -d "${POSTGRES_DB:-mrp}" \
  -c "SELECT count(*) FROM release_volume_probe WHERE token = '$PROBE_TOKEN';")"
if [[ "$PROBE_FOUND" != "1" ]]; then
  echo '[FAIL] PostgreSQL data did not survive container recreation.' >&2
  exit 1
fi
docker compose exec -T db psql -v ON_ERROR_STOP=1 \
  -U "${POSTGRES_USER:-mrp}" -d "${POSTGRES_DB:-mrp}" \
  -c 'DROP TABLE release_volume_probe;' >/dev/null
echo '[OK] PostgreSQL named-volume persistence survived container recreation'

echo '==> Migrations'
run_web python manage.py migrate --noinput

echo '==> Migration drift'
run_web python manage.py makemigrations --check --dry-run

echo '==> Roles'
run_web python manage.py bootstrap_roles

echo '==> Django checks'
run_web python manage.py check
run_web_secure python manage.py check --deploy --fail-level WARNING

echo '==> MRP system check'
run_web python manage.py system_check

echo '==> Tests'
run_web pytest -q

echo '==> Demo factory seed'
run_web python manage.py seed_demo

echo '==> Start application services'
docker compose up -d web worker beat

wait_for 'Web ready' docker compose exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready/', timeout=3)"
wait_for 'Celery worker ping' docker compose exec -T worker celery -A config inspect ping --timeout=5

echo '==> HTTP liveness/readiness'
docker compose exec -T web python - <<'PY'
import urllib.request
for path in ('/health/live/', '/health/ready/'):
    with urllib.request.urlopen('http://127.0.0.1:8000' + path, timeout=10) as r:
        assert r.status == 200, (path, r.status)
        print(path, r.status)
PY

echo "RELEASE_${VERSION//./_}_VALIDATION_OK"
