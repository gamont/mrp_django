# Release 0.8.3

## MRP what-if antes da aprovação do MPS

- Injeção `inline_mps_demands` no motor MRP para simular snapshots sem alterar o MPS compartilhado.
- `MPSRevisionSimulation` e `MPSRevisionSimulationDiffLine`.
- Comparação revision vs baseline/revision em planned orders MAKE, planned orders PURCHASE, mensagens de exceção, pegging e RCCP.
- Suporte síncrono e assíncrono via Celery.
- Política `require_mrp_whatif_before_approval` habilitada por padrão.
- Aprovação de revisão não-baseline bloqueada até existir what-if `COMPLETED`.
- API, UI, comando `simulate_mps_revision`, admin, migração `0024` e documentação.

### Sem efeitos colaterais operacionais

A simulação cria `PlanningRun` e resultados MRP próprios. Não cria `WorkOrder`, `PurchaseOrder` nem publica `MasterProductionSchedule`.
