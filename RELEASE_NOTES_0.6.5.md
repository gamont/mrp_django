# Release 0.6.5 — Solver CP-SAT

- Google OR-Tools CP-SAT como alternativa ao scheduler heurístico.
- Programação global com precedências de OP, máquinas paralelas e recursos alternativos.
- NoOverlap por máquina/recurso e manutenção programada como intervalo fixo.
- Calendário industrial convertido em alternativas de janelas admissíveis.
- Setup dependente da sequência por família na formulação CP-SAT.
- Objetivo ponderado: tardiness, prioridade comercial, makespan, setup e uso de recurso alternativo.
- Persistência de execução, status, objective value, best bound, wall time, branches e conflicts.
- Persistência da atribuição ótima/factível por operação.
- API `/api/schedule-solver-runs/solve/` e comando `solve_cp_sat_schedule`.
- OR-Tools incluído nas dependências da imagem Docker.

Observação: no modo CP-SAT as operações são não-preemptivas e devem caber numa janela contínua do calendário. O modo heurístico anterior continua disponível para operações segmentadas entre turnos.
