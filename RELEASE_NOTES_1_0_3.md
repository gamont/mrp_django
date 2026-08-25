# MRP Django 1.0.3 — Stable release gate hardening

Patch de manutenção da linha 1.0.x, sem alteração de schema ou funcionalidade de domínio.

## Correções
- Remove o pin exato `1.0.2` de `tests/test_release_102_static.py`, que quebraria a próxima release estável.
- Generaliza `scripts/release_consistency.py`: em vez de manter uma lista manual de versões antigas, usa AST para rejeitar qualquer literal exato `1.0.x` dentro de assertions dos testes de release.
- Mantém a regra correta: `VERSION == settings.MRP_VERSION` e, quando necessário, valida somente a linha `1.0.x`.
- Adiciona regressão estática `tests/test_release_103_static.py`.

## Schema
Nenhuma migration nova.

## Homologação
Execute `./scripts/preflight.sh` e depois `./scripts/release_validate.sh` em ambiente Docker.
