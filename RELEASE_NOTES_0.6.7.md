# MRP Django 0.6.7 — CP-SAT preemptivo / segmentável

A versão 0.6.7 amplia o solver CP-SAT com um modo segmentável para operações que podem atravessar pausas, trocas de turno, noite, fins de semana e outras descontinuidades do calendário industrial.

## Destaques

- `ScheduleSolverRun.preemptive_operations` seleciona o modo segmentável.
- `max_consecutive_minutes` limita o tamanho de cada trecho contínuo.
- `handoff_penalty` penaliza interrupções entre segmentos no objetivo do CP-SAT.
- Novo `ScheduleSolverSegment` persiste cada trecho real da solução.
- Todos os segmentos de uma operação permanecem no mesmo recurso na formulação atual.
- Segmentos respeitam `resource_windows()`, `NoOverlap`, manutenção e calendário industrial.
- Precedência tecnológica continua sendo aplicada entre o fim da última parcela de uma operação e o início da próxima.
- Setup dependente da sequência continua aplicado entre operações que compartilham recurso.
- Os segmentos do solver são espelhados em `IntegratedScheduleSegment` quando a solução é aplicada ao cenário.
- UI, API, Celery e CLI recebem os parâmetros do modo preemptivo.

## Nova API

`GET /api/schedule-solver-segments/`

A execução do solver aceita agora:

```json
{
  "preemptive_operations": true,
  "max_consecutive_minutes": 240,
  "handoff_penalty": 5
}
```

## CLI

```bash
python manage.py solve_cp_sat_schedule \
  --scenario 15 \
  --preemptive \
  --max-consecutive-minutes 240 \
  --handoff-penalty 5 \
  --time-limit 120
```

## Migração

`apps/integrated_scheduling/migrations/0008_preemptive_cp_sat_067.py`

## Limites conhecidos

A operação pode ser dividida em vários segmentos, mas todos permanecem na mesma máquina/centro durante uma execução. O tamanho dos segmentos é discretizado pela granularidade do solver e pelo limite de tempo consecutivo configurado. A troca de operador entre turnos é representada como handoff/penalidade; escala individual de operadores ainda não faz parte do CP-SAT.
