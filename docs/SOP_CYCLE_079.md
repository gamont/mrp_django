# S&OP 0.7.9 — ciclo mensal formal

A versão 0.7.9 adiciona governança mensal ao S&OP já existente. Cada ciclo é versionado e percorre as etapas **Demand Review → Supply Review → Pre-S&OP → Executive S&OP → Approved → Published**.

## Versionamento

O código mensal usa `SOP-YYYY-MM`; qualquer nova tentativa/consenso do mesmo mês recebe uma nova versão (`v1`, `v2`, ...). Versões publicadas anteriores do mesmo código são arquivadas quando outra versão é publicada.

## Demand Review

O baseline combina forecast aprovado e pedidos abertos por item/mês. O consenso inicial é `max(forecast, pedidos abertos)`, evitando dupla contagem simples. O ajuste comercial é explícito e guarda justificativa.

## Supply Review

A revisão de suprimento confronta consenso de demanda, estoque inicial e ordens planejadas existentes. O resultado é agregado e deliberadamente não substitui o MRP detalhado.

## Restrições e decisões

`SAndOPConstraint` registra material, capacidade, mão de obra, manutenção, fornecedor, serviço e finanças, com severidade e mitigação. Restrições críticas abertas bloqueiam a aprovação executiva. `SAndOPDecision` mantém dono, prazo e status das decisões do fórum.

## Publicação

Somente ciclos `APPROVED` podem ser publicados. A publicação cria/atualiza entradas `MasterProductionSchedule` com origem `SOP:<ciclo>:v<versão>` e cria um `PlanningRun` em rascunho. O MRP não é executado silenciosamente: a execução permanece uma ação operacional controlada.

## Comandos

```bash
python manage.py run_sop_cycle --plant SP01 --month 2026-08 --horizon-end 2026-10-31
python manage.py publish_sop_cycle --cycle 12
```
