# Release 0.7.3

- `DemandPeggingAllocation` persiste a origem da demanda no MRP.
- Propagação de `SalesOrderLine` pela explosão da BOM.
- `RecoveryCommercialImpact` liga recovery a pedido/linha/cliente e quantidade pegged.
- promessa atual versus promessa recuperada e delta em dias.
- `CommercialPromiseAlert` para pedidos em risco/atraso.
- fallback legado explicitamente rotulado, sem se passar por pegging exato.
- dashboard `/integrated-schedule/commercial-recovery/`.
- APIs `recovery-commercial-impacts` e `commercial-promise-alerts`.
- comando `rebuild_commercial_pegging`.
