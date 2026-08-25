# 0.7.3 — Pegging comercial do recovery

A 0.7.3 persiste a origem da demanda no MRP e a propaga pela explosão da BOM. Uma ordem planejada passa a manter `DemandPeggingAllocation` para `SalesOrderLine`, MPS, forecast ou estoque de segurança. Quando uma ordem planejada é convertida em OP, `WorkOrder.planned_order_id` preserva a ponte para a origem comercial.

O Recovery Control Center usa essa trilha para gerar `RecoveryCommercialImpact`, com pedido, linha, cliente, quantidade pegged, data solicitada, promessa atual, promessa recuperada e status. `CommercialPromiseAlert` registra linhas em risco/atraso para acompanhamento comercial.

## Compatibilidade com histórico

MRP runs executados antes da 0.7.3 não possuem source-aware pegging. Nesses casos o sistema pode continuar exibindo a inferência legada por item/data no resumo operacional, mas ela é rotulada como `LEGACY_INFERRED_BY_ITEM_DATE` e não é apresentada como atribuição comercial exata.

## Comando

`python manage.py rebuild_commercial_pegging --trigger 42`

## Fluxo

SalesOrderLine → MRP demand source → PlannedOrder → WorkOrder → PublishedExecutionSlot → ReschedulingTrigger → RecoveryPlan/CP-SAT → promessa recuperada.
