# Release 0.8.2

## MPS revisioning

- `MPSRevision`, `MPSRevisionLine` e `MPSRevisionRCCPLine`.
- baseline aprovado automaticamente em novos MPS operacionais.
- revisões DRAFT após alterações aplicadas.
- workflow DRAFT → PENDING_APPROVAL → APPROVED/REJECTED.
- regra de dois usuários para aprovação da revisão inteira.
- publicação bloqueada quando a revisão mais recente não está aprovada, salvo `force` explícito.
- rollback cria uma nova revisão, sem apagar a anterior.
- diff item/semana e mudança de status/time fence.
- comparação de sobrecarga RCCP entre revisões.
- impacto MRP identificado explicitamente como estimativa pré-netting.
- API, UI, Admin, comandos de backfill/CLI e testes.

## Upgrade

```bash
python manage.py migrate
python manage.py backfill_mps_revisions
python manage.py check
pytest
```
