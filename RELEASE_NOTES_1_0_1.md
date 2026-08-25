# Release 1.0.1

Release de manutenção e hardening da primeira linha estável.

## Corrigido

- versão hard-coded no `system_check`;
- suposição de que `CELERY_BROKER_URL` sempre aponta para Redis;
- extração frágil de hostname do broker;
- gate de release sem retry explícito de readiness;
- CI sem serviço Redis, apesar do readiness consolidado testar Redis.

## Adicionado

- `REDIS_URL`;
- `scripts/preflight.sh`;
- `scripts/migration_lint.py`;
- `makemigrations --check --dry-run` no gate Docker;
- `system_check` no CI;
- documentação `docs/HARDENING_1_0_1.md`.

## Banco de dados

Sem nova migration de domínio.
