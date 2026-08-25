# MRP/MPS 0.8.4 — impacto financeiro do what-if

A 0.8.4 amplia `MPSRevisionSimulation`: depois de executar o MRP para a revisão de comparação e para a revisão alvo, o sistema calcula uma camada financeira **estimativa** usando os dados de custos já existentes.

## Princípios

- A simulação não publica MPS, não cria OC/OP, não movimenta estoque e não lança contabilidade.
- A versão de custo `ACTIVE` vigente no início do horizonte é preferida; na ausência dela, usa a versão `APPROVED`/`CALCULATED` vigente mais recente. Se nenhuma existir, o status financeiro é `UNAVAILABLE`.
- MAKE usa `ItemCost` da versão de custo para material/subcontratação, mão de obra, máquina, overhead/setup e valor planejado de WIP.
- PURCHASE prefere o preço do fornecedor primário, depois custo médio móvel e depois `ItemCost`.
- `INVENTORY_EXPOSURE` usa o `projected_available` do último bucket MRP do horizonte multiplicado pelo custo de valoração disponível.
- `CASH_OUTFLOW_PROXY` é igual ao gasto planejado de compra e não considera prazo de pagamento, impostos, frete, câmbio ou condições financeiras.
- `WIP_PROXY` representa o valor das recomendações MAKE no horizonte; não é WIP contábil real.

## Saídas

`MPSRevisionSimulation.financial_summary` contém status de cobertura, versão de custo, cobertura percentual, quantidades sem valoração, totais por categoria e definições. `MPSRevisionSimulationFinancialLine` preserva a comparação por item/categoria entre baseline e revisão.

Categorias: `PURCHASE_SPEND`, `MATERIAL_COST`, `LABOR_COST`, `MACHINE_COST`, `OVERHEAD_COST`, `INVENTORY_EXPOSURE`, `WIP_PROXY`, `CASH_OUTFLOW_PROXY`.

## API

O relatório já existente `GET /api/mps-revision-simulations/{id}/report/` passa a incluir `financial_lines` e o serializer da simulação expõe `financial_summary`/`cost_version`. Também existe `GET /api/mps-revision-simulation-financial-lines/` com filtros por simulação, categoria e item.

## Uso

```bash
python manage.py simulate_mps_revision --revision 4 --compare 1
```

A mesma execução 0.8.3 passa a gerar MRP + RCCP + financeiro no relatório único.

Para recalcular apenas a camada financeira de uma simulação 0.8.3 já existente (desde que os dois `PlanningRun` ainda existam):

```bash
python manage.py rebuild_mps_financial_whatif --simulation 17
```
