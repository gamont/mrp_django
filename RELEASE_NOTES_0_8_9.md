# 0.8.9 — CP-SAT Pareto MPS Optimizer

- CP-SAT gera múltiplas distribuições semanais do MPS, preservando totais por item e time fences congelados.
- Cada candidato é avaliado pelo pipeline MRP + RCCP + financeiro + capital de giro + financiamento.
- Classificação por dominância Pareto; score 0.8.8 fica apenas como desempate.
- API `run-pareto`, Celery task, UI da fronteira e comando `optimize_mps_pareto`.
- `service_risk_proxy` é explicitamente prospectivo e não substitui OTIF realizado.
