# Release 0.6.2 — Calendário industrial real

## Novidades

- `respect_industrial_calendar` em cenários integrados (default `True`).
- Operações finitas consumindo somente janelas válidas de capacidade.
- `IndustrialShiftBreak` para pausas fixas por turno.
- `IndustrialCalendarWindow` para hora extra e fechamento parcial por planta/centro/máquina.
- Uso de `ShopCalendarDay` para feriados/dias não úteis e `capacity_factor`.
- Suporte a turnos em sábado/domingo e turnos que cruzam meia-noite.
- `IntegratedScheduleSegment` para operações que atravessam turnos/dias.
- Conflitos de máquina/manutenção passam a considerar segmentos quando presentes.
- Resumo do cenário com segmentos, hora extra efetiva e operações não programadas.
- APIs para pausas, exceções e segmentos.
- Comando `show_industrial_calendar`.
- `simulate_finite_schedule --ignore-calendar` para comparação com o motor 0.6.1.

## Migração

`apps/integrated_scheduling/migrations/0003_industrial_calendar_062.py`

## Compatibilidade

O modelo de bloco e a publicação de `planned_start/planned_end` continuam compatíveis com 0.6.1. Segmentos são uma camada adicional de execução e análise.
