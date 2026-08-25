# MRP 0.6.8

## Mão de obra finita

- Novo modelo de skills e recursos humanos produtivos.
- Integração opcional com `OperatorProfile` e `TechnicianProfile` existentes.
- Turnos por pessoa via `WorkCenterShift`.
- Indisponibilidades por intervalo de data/hora.
- Descanso mínimo simplificado entre alocações.
- Requisito de skill, proficiência e quantidade mínima por `WorkOrderOperation`.
- Restrições CP-SAT conjuntas de máquina + pessoa + calendário.
- `NoOverlap` individual por trabalhador.
- Handoff de equipe entre segmentos no modo preemptivo.
- Continuidade obrigatória de equipe quando `allow_shift_handoff=false`.
- Persistência da equipe escolhida em `ScheduleSolverLaborAssignment`.
- API DRF e Django Admin para os novos cadastros.
- Comando `sync_finite_labor`.
- Flag `--no-labor` no CLI para comparação/diagnóstico.
- Migração `0009_finite_labor_068.py`.

## Validação local

A árvore Python foi compilada e validada por AST. O ambiente de geração não possui Django instalado diretamente; `manage.py check`, migrações e testes de integração devem ser executados dentro do Docker do projeto.
