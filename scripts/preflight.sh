#!/usr/bin/env bash
set -euo pipefail

fail=0
if [[ -n "${COMPOSE_PROJECT_NAME:-}" ]]; then
  echo "[INFO] compose project: ${COMPOSE_PROJECT_NAME}"
fi
for cmd in docker python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[FAIL] comando ausente: $cmd" >&2
    fail=1
  else
    echo "[OK]   $cmd: $(command -v "$cmd")"
  fi
done

if command -v docker >/dev/null 2>&1; then
  if ! docker compose version >/dev/null 2>&1; then
    echo "[FAIL] docker compose indisponível" >&2
    fail=1
  else
    echo "[OK]   docker compose"
    if ! docker compose config --quiet >/dev/null 2>&1; then
      echo "[FAIL] docker-compose.yml/.env inválido para docker compose config" >&2
      fail=1
    else
      echo "[OK]   docker compose config"
    fi
  fi
fi

if [[ ! -f .env ]]; then
  echo "[FAIL] .env ausente. Copie .env.example e ajuste os segredos/hosts." >&2
  fail=1
else
  echo "[OK]   .env presente"
fi

if [[ -f VERSION ]]; then
  echo "[OK]   VERSION=$(tr -d '\r\n' < VERSION)"
else
  echo "[FAIL] VERSION ausente" >&2
  fail=1
fi

python3 scripts/migration_lint.py || fail=1
python3 scripts/release_consistency.py || fail=1
python3 scripts/compose_lint.py || fail=1
python3 scripts/postgres_volume_lint.py || fail=1
python3 scripts/release_gate_lint.py || fail=1
python3 scripts/security_profile_lint.py || fail=1

if (( fail )); then
  echo "PREFLIGHT_FAILED" >&2
  exit 2
fi

echo "PREFLIGHT_OK"
