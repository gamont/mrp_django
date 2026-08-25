# MRP 0.7.0 — Publicação e execução do plano ótimo

A 0.7.0 separa explicitamente **simulação**, **solução do solver** e **cronograma oficial**. Uma execução CP-SAT `OPTIMAL` ou `FEASIBLE` pode ser publicada como uma versão do plano por planta. A publicação cria slots operacionais versionados, registra máquina, centro, equipe prevista e horizonte congelado.

## Fluxo

`CP-SAT -> publicação oficial -> despacho/execução -> planned × actual -> ruptura -> cenário de replanejamento`.

`ProductionSchedulePublication` é a versão oficial. `PublishedExecutionSlot` preserva a linha-base da operação. O campo `frozen` identifica operações dentro do horizonte congelado na publicação. A versão anterior é marcada como `SUPERSEDED`, sem ser apagada.

## Planned × actual

`sync_schedule_execution` lê `WorkOrderOperation.actual_start/actual_end`, atualiza o status do slot e cria desvios de início/fim quando o limiar configurado é excedido. Isso mantém a linha-base original intacta.

## Replanejamento por evento

`ReschedulingTrigger` registra quebra de máquina, falta de material, ausência de operador, mudança de prioridade ou evento manual. O registro é idempotente. A preparação do replanejamento cria um novo `IntegratedScheduleScenario` com referência à publicação oficial e ao evento causador.

A 0.7.0 **não publica automaticamente** um novo cronograma em resposta a uma ruptura. Ela prepara o cenário para nova simulação/CP-SAT e mantém a etapa de publicação como decisão explícita de governança.

## Comandos

```bash
python manage.py publish_optimal_schedule --run 42 --frozen-hours 24
python manage.py sync_schedule_execution --publication 7 --threshold 15
python manage.py trigger_reschedule --plant SP01 --type MACHINE_BREAKDOWN --source-type Machine --source-id 12 --days 14
```
