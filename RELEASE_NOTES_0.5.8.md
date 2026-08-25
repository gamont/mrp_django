# MRP Django 0.5.8

## Planejamento de manutenção e confiabilidade

- Técnicos, skills, proficiência e capacidade diária.
- Atribuição de técnicos e horas planejadas/reais por OM.
- Planner semanal com carga x capacidade.
- SLA por prioridade/planta.
- Verificação de disponibilidade de peças antes da liberação da OM.
- Estado `WAITING_PARTS` quando faltam sobressalentes.
- Leituras e regras de condição para manutenção preditiva.
- Geração idempotente de OM preditiva aberta por regra/título.
- Dashboard de confiabilidade com Pareto de falhas.
- API DRF e Admin para os novos cadastros.
- Migração `maintenance.0002_planning_reliability`.
- Comandos `maintenance_backlog` e `evaluate_maintenance_conditions`.
