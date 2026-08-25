# 0.6.1 — Gantt finito, recursos alternativos e comparação de cenários

A 0.6.1 evolui a programação integrada da 0.6.0 para programação finita por máquina. Cada operação produtiva pode ser atribuída a uma máquina ativa do centro principal; quando o roteiro possui `alternate_work_center`, o simulador também considera as máquinas do centro alternativo.

## Direções de programação

- `FORWARD`: procura o primeiro slot livre a partir da data original.
- `BACKWARD`: procura o slot livre mais tardio antes do fim original.

Manutenções programadas são tratadas como intervalos ocupados. Operações já posicionadas no cenário também ocupam o recurso, evitando sobreposição no mesmo equipamento.

## Gantt interativo

Em `/integrated-schedule/<id>/` as operações aparecem em barras temporais. Blocos produtivos podem ser arrastados horizontalmente; o novo horário é persistido no cenário e o bloco recebe `manually_locked=True`. O ajuste manual não altera a produção real até a publicação do cenário.

## Recursos alternativos

O simulador consulta `RoutingOperation.alternate_work_center`. Um recurso alternativo é escolhido quando produz um resultado melhor no score de atribuição, que penaliza fortemente atraso e, secundariamente, deslocamento temporal e uso de centro alternativo.

## Publicação

Ao aplicar um cenário, além de atualizar `WorkOrderOperation.planned_start`, `planned_end` e `work_center`, a aplicação grava um `PublishedOperationSchedule` com máquina, centro, janela e cenário de origem. Dessa forma a decisão de máquina não se perde após a publicação.

## Comparação

`/integrated-schedule/compare/` ordena cenários por:

1. conflitos críticos;
2. atraso total;
3. conflitos totais;
4. número de operações deslocadas.

A API expõe a mesma comparação em `GET /api/integrated-schedule-scenarios/compare/?scenario=1&scenario=2`.

## CLI

```bash
python manage.py simulate_finite_schedule --plant SP01 --days 14 --direction FORWARD --name "Semana 33"
python manage.py simulate_finite_schedule --plant SP01 --days 14 --direction BACKWARD --name "Entrega puxada"
```
