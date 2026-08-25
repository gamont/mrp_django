# Release 0.8.4 — MPS what-if financeiro

- Avaliação financeira automática ao concluir o MRP what-if de uma revisão MPS.
- Valoração de compras planejadas com fornecedor primário, custo médio móvel ou custo do item, com rastreio da fonte.
- Decomposição MAKE em material, mão de obra, máquina e overhead/setup usando `ItemCost` da versão de custo.
- Proxies explícitos de WIP planejado e saída de caixa; não são lançamentos contábeis.
- Estoque projetado no fim do horizonte valorizado a custo disponível.
- Cobertura de custos e quantidades sem valoração visíveis; status `COMPLETE`, `PARTIAL` ou `UNAVAILABLE`.
- `MPSRevisionSimulationFinancialLine`, `financial_summary` e vínculo opcional à `CostVersion`.
- Relatório HTML e API ampliados para mostrar MRP + RCCP + financeiro em uma única decisão.
- Migração `0025_mps_financial_whatif_084.py`, documentação e testes.
