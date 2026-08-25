# MPS Pareto Optimizer 0.8.9

A versão 0.8.9 adiciona geração de candidatos por OR-Tools CP-SAT e classificação não-dominada (Pareto). O solver preserva o volume total por item e mantém buckets FROZEN fixos. Os objetivos usados dentro do CP-SAT são proxies de diversidade (mudança, nivelamento e preferência temporal); após a geração, cada candidato é submetido ao pipeline real de what-if: MRP, RCCP, custos, cash-flow, capital de giro e financiamento.

## Fronteira
A dominância usa minimização de: risco de serviço prospectivo, overload RCCP, financiamento não coberto, juros, exposição de estoque e compras. `service_risk_proxy` não é OTIF: OTIF realizado depende de entregas reais.

## Governança
Nenhum candidato é publicado automaticamente. A adoção cria uma revisão DRAFT e mantém o fluxo formal de aprovação. Buckets FROZEN não são alterados pelo CP-SAT.
