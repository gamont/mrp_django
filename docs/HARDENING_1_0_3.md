# Hardening 1.0.3 — Testes de release patch-agnostic

## Problema
A 1.0.2 corrigiu pins antigos, mas seu próprio teste passou a exigir literalmente `1.0.2`. Isso recriava a mesma regressão para a release seguinte.

## Regra 1.0.3
Testes da linha estável não podem afirmar igualdade com um patch específico. Devem validar a sincronização entre `VERSION` e `settings.MRP_VERSION` e, se necessário, apenas que a versão pertence à linha `1.0.x`.

## Gate automático
`scripts/release_consistency.py` analisa a AST de `tests/test_release_*.py` e falha quando encontra um literal `1.0.N` dentro de uma expressão `assert`. A detecção não depende de conhecer previamente quais patches já existiram.

## Execução
```bash
python3 scripts/release_consistency.py
./scripts/preflight.sh
./scripts/release_validate.sh
```
