# Programação integrada 0.6.2 — Calendário industrial real

## Objetivo

A 0.6.2 substitui a hipótese de tempo contínuo do scheduler finito 0.6.1 por capacidade temporal executável. A operação continua tendo horas requeridas, mas essas horas são consumidas apenas dentro de janelas válidas do calendário industrial.

## Fontes de capacidade

1. `WorkCenterShift`: turnos regulares por dia da semana, com `capacity_hours` e `efficiency_percent`.
2. `IndustrialShiftBreak`: almoço, refeição, DDS, troca de equipe ou outra pausa fixa dentro do turno.
3. `ShopCalendarDay`: dia útil/não útil e `capacity_factor` por planta; serve para feriados, pontes, redução de jornada e dias especiais.
4. `IndustrialCalendarWindow`: exceções pontuais `OVERTIME` ou `CLOSURE`, podendo valer para planta/centro/máquina.

## Segmentação

Uma operação de 8 h que encontra 4 h úteis na segunda e 4 h na terça gera dois `IntegratedScheduleSegment`. O `IntegratedScheduleBlock.simulated_start/end` continua mostrando o intervalo global para compatibilidade, mas conflitos de máquina e manutenção usam os segmentos quando disponíveis.

## Capacidade variável

`capacity_factor=0.5` em `ShopCalendarDay` reduz pela metade a capacidade efetiva do dia. Assim, 4 horas efetivas podem exigir 8 horas de relógio. O mesmo conceito é usado nas janelas de hora extra.

## Finais de semana e feriados

Sem cadastro explícito, segunda a sexta são úteis. Sábado/domingo passam a ser úteis quando existe turno ativo para aquele weekday. Um `ShopCalendarDay(is_working_day=False)` bloqueia os turnos regulares, mas uma `IndustrialCalendarWindow(OVERTIME)` ainda pode abrir capacidade autorizada.

## Backward scheduling

O modo `BACKWARD` consome as janelas válidas do fim para o início, preservando pausas e indisponibilidades. O modo `FORWARD` faz o mesmo na ordem cronológica.

## Endpoints novos

- `/api/industrial-shift-breaks/`
- `/api/industrial-calendar-windows/`
- `/api/integrated-schedule-segments/`

## Operação

```bash
python manage.py migrate
python manage.py show_industrial_calendar --plant SP01 --center MONT --machine M1 --days 7
python manage.py simulate_finite_schedule --plant SP01 --days 14 --direction FORWARD
```

Para comparar com o comportamento legado 0.6.1:

```bash
python manage.py simulate_finite_schedule --plant SP01 --days 14 --ignore-calendar
```
