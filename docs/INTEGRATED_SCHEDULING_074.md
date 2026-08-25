# 0.7.4 — ATP/CTP comercial e gestão de promessa

A versão 0.7.4 fecha o elo entre planejamento/recovery e atendimento comercial.

## Fluxo

`SalesOrderLine -> ATP + CTP -> SalesOrderPromise(PENDING) -> aprovação/rejeição -> histórico preservado`.

Para recovery, `RecoveryCommercialImpact.recovered_promise_date` pode gerar propostas de promessa associadas ao trigger e ao RecoveryPlan.

## Governança

A execução de ATP/CTP nunca altera silenciosamente a promessa oficial. Ela cria uma proposta pendente. Ao aprovar, a promessa anteriormente aprovada passa a `SUPERSEDED` e o novo registro passa a `APPROVED`.

## Endpoints

- `POST /api/sales-order-promises/evaluate-line/`
- `POST /api/sales-order-promises/{id}/approve/`
- `POST /api/sales-order-promises/{id}/reject/`
- `POST /api/sales-order-promises/from-recovery/`
- `GET /api/commercial-service-cases/`

## UI

`/integrated-schedule/commercial-promises/`

## CLI

`python manage.py evaluate_sales_order_promises --order SO-10582`
