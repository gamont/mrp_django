# Release 0.9.5 — Automatic Audit Anchoring

- Política de ancoragem por planta (`MPSDecisionAnchorPolicy`).
- Ancoragem automática após congelamento do plano oficial.
- Execução diária via Celery Beat.
- Segundo provider de arquivo independente (`FILE_SECONDARY`).
- Painel de proteção com `PROTECTED`, `STALE`, `UNPROTECTED` e `MISMATCH`.
- API e comandos para executar política e consultar cobertura.
- `MRP_VERSION` atualizado para 0.9.5.

A aplicação continua sendo tamper-evident; independência e imutabilidade reais dependem da infraestrutura de storage utilizada.
