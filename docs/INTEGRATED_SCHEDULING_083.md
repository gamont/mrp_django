# MRP 0.8.3 — What-if MRP por revisão do MPS

A versão 0.8.3 executa o MRP em modo what-if diretamente sobre snapshots `MPSRevisionLine`, sem publicar o MPS e sem criar OCs/OPs reais.

## Princípio

Uma revisão alvo é comparada com uma revisão de referência, normalmente o baseline. Cada snapshot é injetado no `PlanningRun.parameters.inline_mps_demands`, portanto o motor MRP usa apenas a demanda daquela revisão. O banco compartilhado de `MasterProductionSchedule` não é alterado pela simulação.

## Comparações

O relatório persiste diferenças de:

- planned orders `MAKE` (recomendações de OP);
- planned orders `PURCHASE` (recomendações de compra);
- mensagens de falta/reprogramação/past-due;
- pegging de componente até item top-level;
- RCCP entre as duas revisões.

A simulação não converte planned orders em `WorkOrder` ou `PurchaseOrder`.

## Governança

`MPSOperationalPolicy.require_mrp_whatif_before_approval=True` por padrão. Assim, uma revisão não-baseline precisa ter pelo menos uma simulação `COMPLETED` antes de ser aprovada.

## CLI

```bash
python manage.py simulate_mps_revision --revision 4
python manage.py simulate_mps_revision --revision 4 --compare 3
```

## API

`POST /api/mps-revision-simulations/run/`

```json
{"revision_id":4,"compare_revision_id":1,"async":false}
```

Use `async=true` para enfileirar no Celery.
