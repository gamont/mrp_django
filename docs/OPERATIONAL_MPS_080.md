# 0.8.0 — S&OP → MPS operacional semanal

A versão 0.8.0 cria uma camada formal entre o ciclo S&OP aprovado e o MRP detalhado.

## Fluxo

`S&OP aprovado → MPS semanal → time fences → RCCP → publicação → PlanningRun → MRP`

## Time fences

A política por planta define Demand Time Fence (DTF) e Planning Time Fence (PTF). Buckets dentro do DTF são `FROZEN`; entre DTF e PTF são `FIRM`; após PTF são `PLANNED`.

## RCCP

O Rough-Cut Capacity Planning usa o roteiro primário dos itens do MPS e acumula `setup + teardown + run_hours_per_unit × quantity` por centro e semana. A capacidade semanal utiliza turnos ativos quando cadastrados; caso contrário, usa a capacidade diária do centro em dias úteis, respeitando `ShopCalendarDay`.

Exceções críticas podem bloquear a publicação conforme a política da planta.

## Governança

Construir o MPS não executa o MRP. Publicar o MPS cria as linhas semanais e prepara um `PlanningRun`. A execução do MRP é uma ação separada e explícita.

## Limites

A desagregação mensal→semanal desta versão distribui quantidades de forma uniforme pelas semanas que intersectam o mês. Perfis sazonais intra-mês e curvas de distribuição específicas por item ficam para evolução posterior.
