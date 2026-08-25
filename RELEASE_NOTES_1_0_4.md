# Release 1.0.4

Release de manutenção/hardening da linha 1.0.x, sem novas migrations de domínio.

## Correções e hardening

- `release_validate.sh` agora coleta `docker compose ps` e logs dos serviços em qualquer falha.
- Cleanup automático do stack de homologação com `docker compose down --remove-orphans`.
- `RELEASE_KEEP_STACK=1` permite manter containers para diagnóstico manual.
- `preflight.sh` valida `docker compose config --quiet` antes do build.
- Novo `scripts/compose_lint.py` protege o contrato mínimo de serviços/healthchecks esperado pelo gate.
- CI executa o novo compose contract lint.
- `release_consistency.py` exige o novo asset de validação.

## Compatibilidade

- Nenhuma migration nova.
- Nenhuma alteração de modelo de domínio.
- Upgrade direto a partir da 1.0.3.
