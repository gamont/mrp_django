# 0.6.5 — Solver CP-SAT

A versão 0.6.5 adiciona uma segunda estratégia de programação ao modo heurístico existente: um modelo de otimização por restrições usando Google OR-Tools CP-SAT.

## O que o solver modela

- precedência tecnológica entre operações da mesma OP;
- escolha entre máquinas paralelas;
- centro alternativo do roteiro;
- `NoOverlap` global por recurso;
- manutenções programadas como intervalos fixos;
- janelas válidas do calendário industrial;
- setups dependentes da sequência entre famílias;
- datas de entrega e tardiness;
- prioridade comercial ponderando atraso;
- makespan e penalidade para recurso alternativo.

O solver usa uma discretização configurável (5 minutos por padrão). Em modo CP-SAT cada operação é não-preemptiva e deve caber em uma janela contínua de calendário. O scheduler heurístico 0.6.2+ continua sendo a opção quando se deseja quebrar uma operação entre turnos/intervalos.

## Status

`OPTIMAL` significa que o CP-SAT provou a otimalidade para o modelo e limites informados. `FEASIBLE` significa que encontrou uma solução, mas não provou o ótimo dentro do time limit.

## Execução

```bash
python manage.py solve_cp_sat_schedule --scenario 15 --time-limit 60 --workers 8 --granularity 5
```

API:

`POST /api/schedule-solver-runs/solve/`

```json
{
  "scenario_id": 15,
  "time_limit_seconds": 60,
  "workers": 8,
  "granularity_minutes": 5,
  "weights": {
    "tardiness": 100,
    "priority_tardiness": 150,
    "makespan": 2,
    "setup": 10,
    "alternate_resource": 5
  }
}
```
