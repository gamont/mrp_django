# Release 0.8.0 — S&OP → MPS operacional semanal

## Destaques
- Desagregação do S&OP mensal em buckets semanais de MPS.
- Política por planta com Demand Time Fence (DTF) e Planning Time Fence (PTF).
- Status automáticos `FROZEN`, `FIRM` e `PLANNED`.
- RCCP semanal por centro de trabalho antes da publicação.
- Exceções de sobrecarga com severidade e workflow.
- Bloqueio opcional da publicação quando existem exceções RCCP críticas abertas.
- Publicação controlada para `MasterProductionSchedule`.
- Criação explícita de `PlanningRun` a partir do MPS operacional.
- Execução do MRP separada da publicação.
- UI, API DRF, Admin, comandos, migração e teste inicial.

## Novos modelos
- `MPSOperationalPolicy`
- `OperationalMPSPublication`
- `MPSWeeklyBucket`
- `MPSRCCPException`

## Migração
`apps/integrated_scheduling/migrations/0021_operational_mps_080.py`

## Validação de geração
- `compileall`: OK
- AST: OK
- integridade ZIP: OK
- `manage.py check`: depende do ambiente Docker com Django instalado.
