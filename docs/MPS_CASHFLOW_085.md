# MPS 0.8.5 — Budget e cash-flow temporal

A 0.8.5 transforma a valoração agregada do what-if 0.8.4 em buckets semanais ou mensais, permitindo comparar **budget × revisão-base × revisão-alvo** antes da aprovação do MPS.

## Regras de timing

- PURCHASE: valor planejado na `release_date + Supplier.payment_terms_days` do fornecedor primário.
- LABOR/MACHINE/OVERHEAD: custos de conversão MAKE na `due_date` planejada.
- INVENTORY_VALUE: `projected_available` de fim do bucket × custo unitário disponível.
- TOTAL_CASH: PURCHASE + LABOR + MACHINE + OVERHEAD.

`TOTAL_CASH` é um proxy de planejamento, não previsão de tesouraria. Não inclui impostos, frete, câmbio, adiantamentos, calendário bancário, faturamento ou contas a pagar reais.

## Budget

`MPSFinancialBudget` possui vigência, planta, bucket semanal/mensal e status. As linhas (`MPSFinancialBudgetLine`) suportam PURCHASE_CASH, LABOR, MACHINE, OVERHEAD, TOTAL_CASH e INVENTORY_VALUE. A simulação usa o budget aprovado que cubra todo o horizonte, ou um budget explicitamente informado.

## Saída

`MPSRevisionSimulationCashFlowBucket` persiste bucket, categoria, baseline, revisão, delta, budget e variância para budget. O relatório what-if exibe os dados temporais junto de MRP, RCCP e impacto financeiro agregado.

## CLI

```bash
python manage.py build_mps_cashflow_whatif --simulation 17
python manage.py build_mps_cashflow_whatif --simulation 17 --budget 3 --bucket-type WEEKLY
```
