# MRP 0.6.9 — Custos e regras de jornada

A versão 0.6.9 estende a capacidade humana finita com regras parametrizáveis. **Não codifica uma legislação específica**: `LaborRuleSet` deve ser configurado segundo convenção, país e política da empresa.

Inclui limites diário/semanal no CP-SAT, custo-base por trabalhador, preferência, overtime no objetivo e cálculo pós-solução de adicional noturno e hora extra. O breakdown é persistido em `ScheduleSolverLaborCost`.

Pesos do solver aceitam `labor_cost`; custos são usados como critério adicional, preservando atraso/setup/prioridade.
