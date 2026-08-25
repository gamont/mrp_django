# MRP Django 0.6.6

> Esta versão adiciona a interface operacional Django + HTMX sobre os módulos MRP/MRP II já existentes.

## Interface operacional

Após iniciar o ambiente, acesse `http://localhost:8000/`. Use um usuário Django existente ou crie um com `python manage.py createsuperuser`. Os painéis disponíveis são Planejamento, Produção, Compras, Estoque, Qualidade e Custos. A planta selecionada fica salva na sessão.

API educacional para planejamento e controle de manufatura, inspirada na organização integrada do COPICS. A versão **0.3.1** estabiliza a base 0.2 com migrações versionadas, concorrência segura no estoque, idempotência reforçada, perfis operacionais, observabilidade, health checks e integração contínua.


## Chão de fábrica 0.5.6 — OEE e Andon

A versão 0.5.6 amplia o terminal de produção com monitoramento diário por máquina. O módulo calcula disponibilidade, performance, qualidade, OEE, MTBF e MTTR; registra o apontamento vinculado à máquina; mantém snapshots diários; e oferece um painel Andon em `/shopfloor/andon/` atualizado por HTMX. Configure em cada máquina `planned_minutes_per_day` e `ideal_cycle_seconds`. Para recalcular por linha de comando: `python manage.py calculate_oee --plant SP01 --date 2026-08-07`.


## Programação integrada 0.6.6 — CP-SAT assíncrono

A 0.6.6 evolui o solver CP-SAT com warm start a partir do melhor cenário heurístico, `relative_gap_limit`, execução assíncrona por Celery/Redis, cancelamento cooperativo, histórico de incumbents e comparação entre heurístico, CP-SAT e cronograma publicado. Para execuções longas, prefira `python manage.py solve_cp_sat_schedule --scenario <id> --time-limit 600 --relative-gap 0.02 --async`. Consulte `docs/INTEGRATED_SCHEDULING_066.md`.

## Stack

- Python 3.12+
- Django 5.2 LTS
- Django REST Framework 3.16
- PostgreSQL 18
- JWT e autenticação por sessão
- Swagger/OpenAPI
- Docker Compose
- Pytest

## Escopo funcional

### Cadastros e engenharia básica

- Plantas e calendário fabril.
- Itens e política de planejamento por planta.
- BOM multinível, efetividade, sucata e low-level code.
- Centros de trabalho, turnos e capacidade efetiva.
- Roteiros, operações e centro de trabalho alternativo.
- Fornecedores e condições item-fornecedor.
- Substitutos de material com prioridade, equivalência e efetividade.

### Demanda e MRP

- Previsão, pedidos de venda e Programa Mestre de Produção.
- Requisitos brutos e líquidos.
- Estoque de segurança.
- Lote por lote, lote fixo, mínimo e múltiplo.
- Lead time em dias úteis.
- Explosão multinível da BOM.
- Ordens planejadas de compra e fabricação.
- Pegging de componente até ordem pai e item de topo.
- Mensagens de liberação, atraso e rescheduling `in/out`.
- Conversão de ordem planejada em OP ou OC.

### Capacidade, ATP, CTP e what-if

- CRP finito por centro de trabalho, calendário e turno.
- Sequenciamento progressivo respeitando a precedência do roteiro.
- Consumo de capacidade distribuído entre release e data prometida.
- Consideração da carga de OPs já liberadas/em andamento.
- Centro de trabalho alternativo.
- CTP com data prometida e indicação de viabilidade.
- ATP com estoque, recebimentos firmes e pedidos abertos.
- Simulação what-if com sobrescrita de horas, eficiência ou fator de capacidade.
- Resumo de gargalos por centro e semana.

### Compras e recebimento

- Recebimento parcial ou total de linha de OC.
- Chave de idempotência para retries seguros.
- Entrada automática no estoque.
- Atualização da quantidade recebida.
- Estado automático da OC: `PARTIAL` ou `COMPLETED`.
- Evento imutável de auditoria.

### Produção e feedback

- Materialização da OP a partir da BOM e do roteiro.
- Liberação com reserva de materiais.
- Uso automático de substitutos aprovados quando houver falta.
- Apontamento parcial ou total da OP.
- Backflush proporcional dos componentes e substitutos efetivamente reservados.
- Baixa das reservas e do estoque.
- Entrada automática do produto acabado.
- Encerramento automático da OP.
- Idempotência no apontamento e trilha de eventos.

### Net-change e auditoria

- Fila de mudanças de demanda, estoque, BOM, política, suprimento, roteiro e capacidade.
- Expansão do item alterado para ancestrais e toda a rede dependente afetada.
- Execução net-change limitada ao escopo afetado.
- Eventos marcados como processados apenas após planejamento concluído.
- `DomainEvent` append-only: não permite alteração nem exclusão.

## Arquitetura

```text
apps/common       planta, calendário, eventos imutáveis e comandos
apps/masterdata   item, política, BOM, substitutos, turnos, roteiro, fornecedor
apps/inventory    armazém, endereço, saldo, reserva e ledger de estoque
apps/demand       previsão, pedido de venda e MPS
apps/planning     MRP, pegging, mensagens, ATP, CRP/CTP, what-if e net-change
apps/production   OP, materiais, operações, apontamentos e backflush
apps/purchasing   OC, recebimento idempotente e fechamento automático
apps/api          serializers, viewsets e rotas DRF
```

## Instalação

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

As migrações iniciais estão versionadas no repositório. O `entrypoint.sh` executa validações, aplica migrações, sincroniza os perfis padrão e coleta os arquivos estáticos antes de iniciar o Gunicorn. Para executar manualmente:

```bash
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py bootstrap_roles
docker compose up -d
```

> **Atualização de uma instalação 0.2:** a versão 0.2 não distribuía migrações iniciais. Em um banco já existente, faça backup e compare o esquema antes de aplicar `migrate --fake-initial`. Em uma instalação nova, use `migrate` normalmente.

Crie o administrador e os dados de demonstração:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo
```

Acessos:

- Swagger: `http://localhost:8000/api/docs/`
- Admin: `http://localhost:8000/admin/`
- JWT: `POST http://localhost:8000/api/token/`
- Liveness: `http://localhost:8000/health/live/`
- Readiness: `http://localhost:8000/health/ready/`
- Métricas: `http://localhost:8000/metrics/`

## Fluxo demonstrativo

### 1. Executar o MRP

```bash
docker compose exec web python manage.py run_mrp --plant SP01 --days 90
```

### 2. Executar CRP finito

Consulte o ID da execução MRP e rode:

```bash
docker compose exec web python manage.py run_crp --planning-run 1
```

Ou pela API:

```http
POST /api/planning-runs/1/crp/
Authorization: Bearer <token>
Content-Type: application/json

{
  "include_open_orders": true,
  "capacity_overrides": {
    "MONT": {"hours_per_day": 16, "efficiency_percent": 90}
  }
}
```

### 3. Consultar ATP

```http
POST /api/items/1/atp/
Authorization: Bearer <token>
Content-Type: application/json

{
  "plant": 1,
  "quantity": "50",
  "requested_date": "2026-09-01",
  "horizon_days": 365
}
```

### 4. Consultar CTP

```http
POST /api/items/1/ctp/
Authorization: Bearer <token>
Content-Type: application/json

{
  "plant": 1,
  "quantity": "100",
  "release_date": "2026-08-10",
  "due_date": "2026-08-21",
  "include_open_orders": true,
  "capacity_overrides": {}
}
```

A resposta informa `feasible`, `promised_date`, horas carregadas e gargalos.

### 5. Executar what-if

```http
POST /api/capacity-scenarios/what-if/
Authorization: Bearer <token>
Content-Type: application/json

{
  "plant": 1,
  "item": 1,
  "quantity": "150",
  "release_date": "2026-08-10",
  "due_date": "2026-08-28",
  "include_open_orders": true,
  "capacity_overrides": {
    "TESTE": {"factor": "2"}
  }
}
```

Gargalos de um cenário:

```http
GET /api/capacity-scenarios/1/bottlenecks/
```

### 6. Receber uma compra

A OC precisa estar `RELEASED` ou `PARTIAL`:

```http
POST /api/purchase-order-lines/10/receive/
Authorization: Bearer <token>
Content-Type: application/json

{
  "quantity": "25",
  "destination_location": 1,
  "receipt_number": "REC-2026-001",
  "idempotency_key": "erp-rec-2026-001-line-10",
  "lot_number": "L260805"
}
```

Repetir exatamente a mesma chave não duplica o recebimento.

### 7. Liberar e encerrar uma OP

```http
POST /api/work-orders/15/release/
Authorization: Bearer <token>
```

```http
POST /api/work-orders/15/complete/
Authorization: Bearer <token>
Content-Type: application/json

{
  "good_quantity": "100",
  "scrap_quantity": "2",
  "destination_location": 2,
  "idempotency_key": "mes-op15-apontamento-final",
  "backflush": true,
  "notes": "Produção concluída"
}
```

### 8. Executar net-change

Alterações nos principais registros criam eventos pendentes. Para processá-los:

```http
POST /api/planning-runs/net-change/
Authorization: Bearer <token>
Content-Type: application/json

{
  "plant": 1,
  "horizon_start": "2026-08-05",
  "horizon_end": "2026-11-03",
  "include_sales_orders": false,
  "include_forecasts": false
}
```

Ou por comando:

```bash
docker compose exec web python manage.py run_net_change --plant SP01 --days 90
```

## Endpoints funcionais da versão 0.2

```text
GET/POST /api/item-substitutes/
GET/POST /api/work-center-shifts/
POST     /api/items/{id}/atp/
POST     /api/items/{id}/ctp/
POST     /api/planning-runs/{id}/crp/
POST     /api/planning-runs/net-change/
GET/POST /api/capacity-scenarios/
POST     /api/capacity-scenarios/{id}/execute/
POST     /api/capacity-scenarios/what-if/
GET      /api/capacity-scenarios/{id}/bottlenecks/
GET      /api/capacity-allocations/
GET      /api/planning-changes/
POST     /api/purchase-order-lines/{id}/receive/
POST     /api/work-orders/{id}/complete/
GET      /api/work-order-completions/
GET      /api/domain-events/
```

## Regras importantes

1. O MPS é a demanda independente principal do MRP.
2. Pedidos e previsão são opcionais para evitar dupla contagem.
3. O saldo inicial é `on_hand - allocated`.
4. O MRP considera OCs liberadas/parciais e OPs liberadas/em andamento como recebimentos programados.
5. A BOM é explodida na data de liberação do pai.
6. O pegging mantém a ligação até o item de topo.
7. O CRP é finito: quando não há capacidade no dia, a carga avança para o próximo dia útil.
8. Turnos ativos substituem a capacidade diária padrão do centro naquele dia da semana.
9. Substitutos são usados por prioridade e relação de equivalência.
10. Recebimentos e apontamentos exigem chave de idempotência.
11. Eventos de domínio são append-only.
12. Net-change só marca eventos como processados depois do MRP concluído.

## Estabilização 0.3.1

### Migrações e integridade

- Migrações iniciais versionadas para todos os aplicativos com modelos.
- `CheckConstraint` para quantidades, datas, percentuais e saldos não negativos.
- Índices explícitos para ordens, movimentos, pegging, capacidade, mensagens e eventos.
- Verificação de migrações ausentes no pipeline de CI.

### Concorrência e idempotência

- Bloqueio pessimista com `select_for_update()` em saldos, OCs, OPs, reservas e apontamentos.
- Saldos bloqueados em ordem determinística para reduzir deadlocks em transferências opostas.
- Chaves de idempotência protegidas também contra corrida entre processos.
- Reutilizar uma chave com payload diferente gera erro de validação.
- Movimentações genéricas não podem consumir quantidade já reservada.

### Perfis operacionais

O comando abaixo cria ou atualiza os grupos e as permissões Django:

```bash
docker compose exec web python manage.py bootstrap_roles
```

Grupos padrão:

- `MRP Administradores`
- `MRP Planejadores`
- `MRP Compradores`
- `MRP Produção`
- `MRP Almoxarifado`
- `MRP Vendas`
- `MRP Auditores`

Todos os grupos recebem permissões de consulta. Alterações são concedidas conforme a função; exclusões permanecem reservadas aos administradores. A API usa as permissões de modelo do Django como política global e define permissões específicas para ações como MRP, CRP, recebimento e encerramento de OP.

### Observabilidade e operação

- Logs JSON com `request_id`, rota, status, duração e usuário.
- Propagação e retorno do cabeçalho `X-Request-ID`.
- Endpoint de liveness sem dependências externas.
- Endpoint de readiness verificando banco e migrações pendentes.
- Métricas HTTP em formato Prometheus.
- Token opcional para `/metrics/` via `MRP_METRICS_TOKEN`.
- Health check do serviço web no Docker Compose.

Detalhes adicionais: [Operação e observabilidade](docs/OPERATIONS.md) e [Perfis e permissões](docs/RBAC.md).

## Testes e validações

```bash
docker compose run --rm web pytest
docker compose run --rm web coverage run -m pytest
docker compose run --rm web coverage report
```

Validação completa usada no CI:

```bash
make ci
```

A suíte cobre:

- explosão da BOM e pegging;
- atualização de estoque;
- recebimento de compra idempotente;
- fechamento automático da OC;
- reserva e backflush com substituto;
- entrada do produto acabado e encerramento da OP;
- CTP finito e data prometida;
- expansão da rede no net-change.

## Próximas evoluções

- Revisões de engenharia/ECO com workflow formal de aprovação.
- Controle quantitativo por lote e número de série.
- Inspeção, quarentena e shelf life integrados ao saldo disponível.
- Custos padrão, reais e variações industriais.
- Dashboard operacional em templates/HTMX.
- Execução assíncrona com fila de tarefas.


## Engenharia e ECO — 0.3.1

A versão 0.3.1 adiciona workflow formal de alteração de engenharia, aprovações sequenciais, análise de impacto, revisões de BOM/roteiro e efetividade por data, lote, série, quantidade, esgotamento ou outra ECO. A ativação de uma revisão substitui a BOM vigente, registra evento de domínio e cria mudanças para net-change MRP.

### Fluxo da ECO
`DRAFT → ANALYSIS → APPROVAL → APPROVED/SCHEDULED → EFFECTIVE → CLOSED`

### Endpoints
- `POST /api/engineering-changes/{id}/analyze-impact/`
- `POST /api/engineering-changes/{id}/submit/`
- `POST /api/engineering-changes/{id}/approve/`
- `POST /api/engineering-changes/{id}/reject/`
- `POST /api/engineering-changes/{id}/activate/`
- CRUD de itens, aprovações, revisões de BOM e roteiro.

## Versão 0.3.4 — Recall e rastreabilidade integrada

- Casos de recall com workflow de investigação, aprovação, execução e conclusão.
- Critérios por lote, série, item, fornecedor, período e referência de origem.
- Expansão automática da genealogia para componentes e where-used.
- Bloqueio coordenado de lotes e números de série afetados.
- Registro de unidades afetadas, ações, responsáveis e disposição final.
- Resumo operacional e eventos de domínio imutáveis.

Consulte `docs/RECALL.md`.


## Custos industriais 0.4.0

Inclui custo padrão, roll-up da BOM, custo planejado e real por OP, custos de material/mão de obra/máquina/overhead/refugo, PPV e análise de variações. Consulte `docs/COSTING.md`.

## Versão 0.4.1 — Valorização de Estoque, WIP e Fechamento de Custos

A versão 0.4.1 acrescenta períodos contábeis industriais e snapshots reprodutíveis de valorização.

### Novos recursos

- Período de custos por planta (`AccountingPeriod`).
- Valorização de estoque por custo padrão ativo.
- Detalhamento por item e localização.
- Snapshot de WIP para OPs liberadas/em andamento.
- Separação entre valor incorrido, produção completada e WIP remanescente.
- Fechamento transacional do período com `select_for_update()`.
- Bloqueio de recálculo após fechamento.
- API DRF e comandos de gerenciamento.

### Endpoints

```text
GET/POST /api/accounting-periods/
POST     /api/accounting-periods/{id}/inventory-valuation/
POST     /api/accounting-periods/{id}/wip-valuation/
POST     /api/accounting-periods/{id}/close/
GET      /api/inventory-valuations/
GET      /api/wip-valuations/
```

### Comandos

```bash
python manage.py run_inventory_valuation --plant SP01 --period 2026-08
python manage.py run_wip_valuation --plant SP01 --period 2026-08
python manage.py close_cost_period --plant SP01 --period 2026-08
```


## Versão 0.4.2 — custo médio móvel e subledger de custos

- Custo médio móvel por planta/item.
- Histórico financeiro por movimentação de estoque.
- Valorização de inventário por STANDARD ou MOVING_AVERAGE.
- Subledger de custos com partidas de débito/crédito.
- Consolidação e lançamento das variações do período.
- Lançamentos de estoque e WIP no fechamento.

Comandos:

```bash
python manage.py rebuild_moving_average --plant SP01
python manage.py post_period_variances --plant SP01 --period 2026-08
```

## Versão 0.4.3 — Reavaliação e conciliação

A versão 0.4.3 acrescenta reavaliação financeira de estoque, ajustes financeiros, custo real por lote/série e conciliação físico × financeiro.

### Endpoints

```text
POST /api/inventory-revaluations/post/
GET  /api/inventory-revaluations/
GET/POST /api/financial-inventory-adjustments/
POST /api/financial-inventory-adjustments/{id}/post/
GET  /api/lot-actual-costs/
POST /api/lot-actual-costs/calculate/
GET  /api/serial-actual-costs/
POST /api/serial-actual-costs/calculate/
GET  /api/inventory-reconciliations/
POST /api/inventory-reconciliations/run/
```

### Comandos

```bash
python manage.py revalue_inventory_item --plant SP01 --item LED-001 --unit-cost 18.75 --reason "Revisão de custo" --key reval-2026-08-led001
python manage.py run_inventory_reconciliation --plant SP01 --period 2026-08
```

## Versão 0.4.4 — Fechamento industrial definitivo

A 0.4.4 adiciona fechamento definitivo com reconciliação opcionalmente estrita, validação de débito/crédito do subledger, trilha de auditoria append-only, estornos, reabertura controlada com aprovação e relatório consolidado de custos por período.

Principais endpoints:

- `POST /api/accounting-periods/{id}/final-close/`
- `GET /api/accounting-periods/{id}/cost-report/`
- `POST /api/period-reopen-requests/request/`
- `POST /api/period-reopen-requests/{id}/approve/`
- `POST /api/period-reopen-requests/{id}/reject/`
- `POST /api/period-reopen-requests/{id}/apply/`
- `POST /api/cost-ledger-reversals/reverse/`
- `GET /api/cost-period-audit/`

Veja `docs/COST_PERIOD_CLOSE_044.md`.
## Interface operacional 0.5.1

Além dos dashboards da 0.5.0, a UI agora permite executar as principais transações do dia a dia com HTMX: firmar/converter ordens MRP, liberar/apontar OP, receber OC, iniciar/finalizar inspeção e fechar período industrial. Consulte `docs/UI_051.md`.


## Interface operacional 0.5.2

A versão 0.5.2 adiciona telas de detalhe para ordem planejada, OP, OC, inspeção e custo de item. Consulte `docs/UI_052.md`. Não há migração nova nesta versão.


## Interface operacional 0.5.3

A versão 0.5.3 permite editar a execução diretamente nas telas de detalhe: controlar estados de operações da OP, apontar produção por operação, baixar material principal/substituto e registrar resultados de inspeção por característica. As ações usam HTMX com fallback HTML e permissões Django no servidor. Consulte `docs/UI_053.md`. Não há migração nova nesta versão.


## Versão 0.5.4 — Terminal de chão de fábrica

A interface inclui um terminal touch em `/shopfloor/login/`, com crachá + PIN, seleção de estação, fila de operações por centro de trabalho, despacho da próxima operação, setup/execução/pausa/conclusão, apontamento de produção, status de máquina e registro de paradas.

```bash
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py bootstrap_roles
docker compose run --rm web python manage.py seed_shopfloor --plant SP01
docker compose run --rm web python manage.py set_operator_pin --username operador --badge 1001 --pin 123456
```

Consulte `docs/UI_054.md`.


## OEE 0.5.6

A versão 0.5.6 adiciona OEE por turno, metas com vigência, perdas OEE, Pareto de paradas e histórico operacional.

```bash
python manage.py calculate_oee --plant SP01 --include-shifts
python manage.py calculate_oee_history --plant SP01 --from 2026-07-01 --to 2026-08-07
```

Dashboard histórico: `/shopfloor/oee/history/`. Consulte `docs/UI_056.md`.

## Versão 0.5.7 — Manutenção industrial integrada ao OEE

A 0.5.7 adiciona ativos, planos preventivos por calendário/medidor, ordens de manutenção, falhas, peças de reposição e integração automática com status de máquina, paradas e OEE/MTBF/MTTR.

```bash
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py bootstrap_roles
docker compose run --rm web python manage.py seed_maintenance --plant SP01
docker compose run --rm web python manage.py generate_maintenance_orders --plant SP01
```

Dashboard: `/maintenance/`. Consulte `docs/UI_057.md`.

## Versão 0.5.8 — Planejamento de manutenção e confiabilidade

A 0.5.8 adiciona planejamento semanal de manutenção, técnicos/skills, carga da equipe, SLA, validação de sobressalentes antes da liberação da OM, manutenção baseada em condição e Pareto de falhas.

### Rotas

- `/maintenance/planner/` — planejamento semanal e carga da equipe.
- `/maintenance/reliability/` — confiabilidade e Pareto.
- `/api/maintenance-technicians/`
- `/api/maintenance-technician-skills/`
- `/api/maintenance-work-order-assignments/`
- `/api/maintenance-slas/`
- `/api/maintenance-condition-readings/`
- `/api/maintenance-condition-rules/`

### Operação

```bash
python manage.py migrate
python manage.py maintenance_backlog --plant SP01
python manage.py evaluate_maintenance_conditions --plant SP01
```


## Versão 0.5.9 — Programação avançada da manutenção

A 0.5.9 acrescenta backlog Kanban, calendário drag-and-drop, priorização por criticidade/SLA/OEE, alocação automática de técnicos por skill/capacidade, reserva de peças e conflitos manutenção × produção. Veja `docs/UI_059.md`.

## 0.6.0 — Programação integrada Produção + Manutenção

Acesse `/integrated-schedule/` para criar cenários what-if que combinam OPs e manutenção na mesma visão de capacidade. A simulação calcula perda de capacidade, sobreposições, sobrecarga e risco de atraso, sem alterar as operações reais até o cenário ser aplicado explicitamente.

Comando de exemplo:

```bash
python manage.py simulate_integrated_schedule --plant SP01 --days 14 --name "Preventivas agosto"
```

Consulte `docs/INTEGRATED_SCHEDULING_060.md`.


## 0.6.1 — Gantt finito e múltiplos cenários

A programação integrada agora é finita por máquina, suporta `FORWARD` e `BACKWARD`, centro alternativo do roteiro, ajuste manual por Gantt e publicação persistente da máquina escolhida em `PublishedOperationSchedule`. A tela `/integrated-schedule/compare/` permite comparar cenários antes de publicar.

```bash
python manage.py simulate_finite_schedule --plant SP01 --days 14 --direction FORWARD --name "Semana 33"
```

Consulte `docs/INTEGRATED_SCHEDULING_061.md`.

## 0.6.2 — Calendário industrial real

O scheduler finito passa a respeitar turnos, pausas, finais de semana, feriados/dias não úteis, capacidade variável e janelas de hora extra/fechamento. Operações podem atravessar vários turnos sem ocupar artificialmente a máquina durante a noite: os trechos executáveis ficam registrados em `IntegratedScheduleSegment`.

```bash
python manage.py simulate_finite_schedule --plant SP01 --days 14 --direction FORWARD
python manage.py show_industrial_calendar --plant SP01 --center MONT --machine M1 --days 7
```

Cadastros relevantes: `ShopCalendarDay`, `WorkCenterShift`, `IndustrialShiftBreak` e `IndustrialCalendarWindow`. Consulte `docs/INTEGRATED_SCHEDULING_062.md`.

## 0.6.3 — Sequência finita avançada

O scheduler integrado agora suporta famílias de produto, matriz de troca dependente da sequência, campanhas e regras de despacho `EDD`, `SPT`, `CR`, `PRIORITY` e `SETUP_MIN`. O setup de troca consome capacidade efetiva do calendário industrial e entra na escolha da melhor máquina/recurso.

Principais cadastros:

- `ProductFamily`
- `ItemSchedulingProfile`
- `SequenceSetupRule`

Exemplo de execução:

```bash
python manage.py simulate_sequence_schedule \
  --plant SP01 \
  --days 14 \
  --rule SETUP_MIN \
  --campaign \
  --name "Campanha faróis semana 33"
```

Documentação detalhada: `docs/INTEGRATED_SCHEDULING_063.md`.


## 0.6.4 — Otimizador multicritério

A programação integrada agora pode gerar automaticamente vários cenários candidatos e ranqueá-los por uma função multicritério configurável. Os objetivos iniciais são atraso total, setup, hora extra, atraso ponderado pela prioridade comercial, desequilíbrio de utilização entre recursos e conflitos. Os KPIs são normalizados dentro da execução, os pesos são normalizados para somar 1 e cenários com conflitos críticos recebem penalidade de inviabilidade.

Além do ranking por score ponderado, a versão identifica a fronteira de Pareto. Cada candidato continua sendo um `IntegratedScheduleScenario` completo e pode ser aberto, analisado, ajustado manualmente e publicado pelos fluxos existentes.

Exemplo CLI:

```bash
python manage.py optimize_schedule --scenario 15 --candidates 8 --w-lateness 0.35 --w-setup 0.20 --w-overtime 0.15 --w-priority 0.15 --w-utilization 0.05 --w-conflicts 0.10
```

## 0.6.5 — Solver CP-SAT / OR-Tools

Além do otimizador heurístico multicritério, o projeto possui agora um solver global por restrições com Google OR-Tools CP-SAT. Ele trata precedências, máquinas paralelas, recurso alternativo, calendário industrial, manutenção fixa, setup dependente da sequência, tardiness e prioridade comercial.

```bash
python manage.py solve_cp_sat_schedule --scenario 15 --time-limit 60 --workers 8 --granularity 5
```

Status `OPTIMAL` significa que a otimalidade foi provada para a formulação e limite de tempo; `FEASIBLE` indica uma solução válida sem prova do ótimo. Veja `docs/INTEGRATED_SCHEDULING_065.md`.

## 0.6.7 — CP-SAT preemptivo / segmentável

O solver possui agora um modo opcional para dividir uma operação em múltiplos segmentos de execução. Isso permite atravessar almoço, troca de turno, noite, fim de semana e outras lacunas do calendário sem exigir que a operação caiba em uma única janela contínua.

Exemplo:

```bash
python manage.py solve_cp_sat_schedule \
  --scenario 15 \
  --preemptive \
  --max-consecutive-minutes 240 \
  --handoff-penalty 5 \
  --time-limit 120
```

Os trechos resolvidos são persistidos em `ScheduleSolverSegment` e espelhados em `IntegratedScheduleSegment` quando o resultado é aplicado ao cenário. Veja `docs/INTEGRATED_SCHEDULING_067.md`.

## 0.6.8 — Mão de obra finita integrada ao CP-SAT

O solver passa a restringir simultaneamente **máquina + mão de obra + calendário**. Operações podem exigir uma ou mais skills, proficiência mínima e quantidade mínima de pessoas. Os trabalhadores possuem turno, indisponibilidades e descanso mínimo entre alocações; no modo preemptivo a equipe pode trocar entre segmentos/turnos, ou permanecer fixa quando o requisito proíbe handoff.

Principais cadastros:

- `LaborSkill`
- `LaborResource`
- `LaborResourceSkill`
- `LaborShiftAssignment`
- `LaborUnavailability`
- `OperationLaborRequirement`
- `ScheduleSolverLaborAssignment`

Sincronize operadores/técnicos existentes:

```bash
python manage.py sync_finite_labor --plant SP01
```

Resolva com mão de obra finita (padrão):

```bash
python manage.py solve_cp_sat_schedule \
  --scenario 15 \
  --preemptive \
  --max-consecutive-minutes 240 \
  --time-limit 300
```

Para diagnóstico/comparação sem a dimensão humana use `--no-labor`. Veja `docs/INTEGRATED_SCHEDULING_068.md`.


## 0.6.9 — Custos e regras de jornada no solver

Adiciona política parametrizável de jornada, limite diário/semanal, custo hora, preferência de operador, custo de hora extra e adicional noturno. O CP-SAT passa a considerar custo de mão de obra no objetivo e persiste um breakdown financeiro por alocação. Consulte `docs/INTEGRATED_SCHEDULING_069.md`.

## 0.7.1 — Publicação e execução do plano ótimo

A camada de programação integrada agora possui uma linha clara entre cenário, execução do CP-SAT e cronograma oficial. `ProductionSchedulePublication` versiona o plano por planta; `PublishedExecutionSlot` preserva a linha-base por operação, máquina e equipe; `ScheduleExecutionDeviation` registra planned × actual; e `ReschedulingTrigger` prepara cenários de replanejamento após rupturas operacionais.

Comandos principais:

```bash
python manage.py publish_optimal_schedule --run 42 --frozen-hours 24
python manage.py sync_schedule_execution --publication 7 --threshold 15
python manage.py trigger_reschedule --plant SP01 --type MACHINE_BREAKDOWN --source-type Machine --source-id 12
```

Veja `docs/INTEGRATED_SCHEDULING_070.md`.

## 0.7.1 — Recovery scheduling automático
- DowntimeEvent e ausência de mão de obra geram triggers automáticos quando impactam o cronograma publicado.
- Scan de falta real de materiais por reservas de OP (`scan_schedule_shortages`).
- CP-SAT recovery via Celery, com frozen horizon preservado.
- Tela/API de comparação plano atual × recuperado antes da publicação.
- Publicação de recovery mantém slots congelados da versão anterior.


## 0.7.2 — Recovery Control Center

Fila centralizada de rupturas com severidade, ETA, impacto operacional/comercial, múltiplos planos de recuperação, score de risco e política opcional de auto-publicação apenas para planos de baixo risco. A atribuição comercial nesta versão é inferida por item/data; use pegging para atribuição contratual exata.

Comando: `python manage.py recovery_control_center --plant SP01`. Interface: `/integrated-schedule/recovery-control/`.

## 0.7.3 — Pegging comercial e promessa recuperada

A release 0.7.3 adiciona source-aware pegging no MRP até `SalesOrderLine`, impacto comercial exato no Recovery Control Center, promessa atual versus recuperada e alertas internos para atendimento comercial. Consulte `docs/INTEGRATED_SCHEDULING_073.md`.

## 0.7.4 — ATP/CTP comercial

A camada comercial agora calcula ATP/CTP por linha de pedido, cria propostas de nova promessa, preserva histórico de aprovação/rejeição e mantém uma fila operacional de atendimento comercial. Veja `docs/INTEGRATED_SCHEDULING_074.md`.

## 0.7.5 — confirmação comercial

A promessa comercial agora possui contato, comunicação externa, resposta do cliente e compromisso efetivo. Após aceite, a data confirmada passa a orientar o próximo MRP/ATP; a data contratual original permanece preservada em `SalesOrderLine.requested_date`.

Comandos úteis:

```bash
python manage.py send_customer_promise --promise 123 --channel EMAIL
python manage.py register_customer_promise_response --promise 123 --response ACCEPTED --date 2026-08-15
```


## 0.7.6 — OTIF e nível de serviço

Adiciona entregas comerciais reais (`SalesDelivery`/`SalesDeliveryLine`), cálculo de On-Time, In-Full e OTIF por linha, três referências de compromisso (solicitada, promessa aprovada e aceite do cliente), causas de atraso baseadas em evidência operacional e comando `evaluate_otif`.

## 0.7.7 — OTIF gerencial e nível de serviço

A versão 0.7.7 adiciona metas de serviço por planta/cliente/família/item, snapshots mensais, fill rate, backlog vencido, Pareto de causas, tendência histórica e custo estimado da falha de serviço. A métrica Perfect Order é apresentada como **proxy** (OTIF em uma única remessa), pois acurácia documental/faturamento e avarias ainda não estão modeladas.

```bash
python manage.py seed_service_level_targets --plant SP01
python manage.py build_service_level_snapshots --plant SP01 --year 2026 --month 8 --reference CUSTOMER_ACCEPTED
```

Dashboard: `/integrated-schedule/service-level/management/`.


## 0.7.8 — S&OP / Executive Service Dashboard

Adiciona forecast accuracy por WAPE, snapshot executivo mensal (OTIF, fill rate, backlog, estoque, OEE, capacidade, demanda e suprimento), receita em risco com cobertura explícita de preços e cenários what-if agregados de demanda/capacidade/estoque. Use `python manage.py build_executive_sop --plant SP01 --year 2026 --month 8`.

## 0.7.9 — ciclo S&OP mensal formal

A versão 0.7.9 formaliza o S&OP mensal: versões do plano, baseline de demanda, consenso comercial, Supply Review, registro de restrições, Pre-S&OP, Executive S&OP, decisões com responsáveis/prazos, aprovação e publicação controlada em MPS. A publicação cria um `PlanningRun` em rascunho; o MRP continua sendo executado explicitamente. Consulte `docs/SOP_CYCLE_079.md`.

## 0.8.0 — MPS operacional semanal

A 0.8.0 adiciona a ponte governada entre o ciclo S&OP aprovado e o MRP: desagrega o plano mensal em buckets semanais, aplica time fences, executa RCCP e só então publica o MPS operacional e prepara o `PlanningRun`.

Comandos principais:

```bash
python manage.py seed_mps_operational_policy --plant SP01 --dtf 14 --ptf 42
python manage.py build_operational_mps --plant SP01 --cycle SOP-2026-08 --publish
python manage.py build_operational_mps --plant SP01 --cycle SOP-2026-08 --publish --run-mrp
```

Documentação: `docs/OPERATIONAL_MPS_080.md`.

## 0.8.1 — MPS operacional interativo

A 0.8.1 permite editar e redistribuir buckets semanais antes da publicação. O baseline vindo do S&OP é preservado, o delta é visível, o RCCP é recalculado após as alterações e qualquer mudança em bucket `FROZEN` exige aprovação por outro usuário através de `MPSBucketChangeRequest`.

## 0.8.2 — versionamento e comparação do MPS

A 0.8.2 preserva revisões completas do MPS semanal, oferece diff por item/semana, compara impacto RCCP e impacto estimado pré-MRP, exige aprovação da revisão inteira antes da publicação e suporta rollback sem apagar histórico.

Após atualizar uma base 0.8.1, crie snapshots baseline para publicações existentes:

```bash
python manage.py backfill_mps_revisions
```

Documentação: `docs/OPERATIONAL_MPS_082.md`.

## 0.8.3 — MRP what-if por revisão

Antes de aprovar uma revisão do MPS operacional, o sistema pode executar o netting MRP sobre o snapshot da revisão e compará-lo com o baseline (ou outra revisão). O relatório mostra diferenças em recomendações MAKE/PURCHASE, mensagens de exceção, pegging e RCCP sem publicar o MPS nem criar documentos reais.

```bash
python manage.py simulate_mps_revision --revision 4
```

A política padrão `require_mrp_whatif_before_approval=True` bloqueia a aprovação de revisões não-baseline sem uma simulação concluída.

## 0.8.4 — impacto financeiro do MRP what-if

A simulação de revisão MPS agora calcula, no mesmo relatório, impacto estimado de compras, material, mão de obra, máquina, overhead/setup, estoque projetado, WIP proxy e caixa proxy. A valoração usa a versão de custo vigente e informa explicitamente cobertura e itens/quantidades sem custo; nenhum valor é lançado na contabilidade.

```bash
python manage.py simulate_mps_revision --revision 4 --compare 1
```

Documentação: `docs/MPS_FINANCIAL_WHATIF_084.md`.


## 0.8.5 — Budget e cash-flow temporal do MPS
A simulação MPS what-if agora temporaliza compras conforme prazo de pagamento do fornecedor, custos de conversão MAKE e estoque projetado, comparando baseline × revisão × budget em buckets semanais ou mensais. Consulte `docs/MPS_CASHFLOW_085.md`.


## 0.8.6 — Capital de giro do MPS what-if
A simulação de revisão do MPS agora projeta AR, AP, estoque em valor, entradas/saídas, caixa acumulado e pico de necessidade de capital de giro. Condições comerciais podem ter parcelas em JSON; DIO/DSO/DPO e Cash Conversion Cycle são proxies de planejamento e não saldos contábeis. Use `python manage.py build_mps_working_capital_whatif --simulation <id>` para reconstruir uma simulação existente.

## 0.8.7 — capacidade financeira
A simulação MPS agora encadeia MRP → RCCP → custo → cash-flow → capital de giro → financiamento. Linhas de crédito por planta permitem medir pico de utilização, juros estimados e necessidade não coberta; a política financeira pode bloquear a aprovação de uma revisão financeiramente inviável. Consulte `docs/MPS_FINANCING_087.md`.

## 0.8.8 — otimização multicritério do MPS

A 0.8.8 adiciona geração e ranking de alternativas para revisões do MPS. As estratégias iniciais redistribuem volume entre semanas não congeladas, nivelam buckets e avaliam fornecedores alternativos com prazo financeiro melhor. Cada candidato passa pelo pipeline MRP what-if + RCCP + custo + cash-flow + capital de giro + financiamento. O resultado é um score configurável e uma recomendação explicável. Nenhum candidato é publicado ou aprovado automaticamente; a adoção de buckets cria uma nova revisão formal, enquanto troca de fornecedor permanece recomendação de sourcing para Compras.

Comando principal:

```bash
python manage.py optimize_mps_revision --revision 4 --compare 1
```

Detalhes em `docs/MPS_OPTIMIZER_088.md` e `RELEASE_NOTES_0_8_8.md`.


## 0.8.9 — CP-SAT Pareto MPS Optimizer

Geração de múltiplos candidatos por OR-Tools CP-SAT e fronteira Pareto sobre risco de serviço prospectivo, RCCP, financiamento, juros, estoque e compras. Consulte `docs/MPS_PARETO_OPTIMIZER_089.md`.


## 0.9.0 — Cockpit executivo de decisão MRP/MPS

A 0.9.0 transforma a fronteira Pareto em um processo formal de decisão. Uma otimização CP-SAT concluída pode ser aberta em um cockpit com gráfico interativo, comparação lado a lado, shortlist, justificativa, aprovação executiva por segundo usuário e congelamento do cenário escolhido como nova revisão oficial do MPS. O congelamento não publica o `MasterProductionSchedule` nem executa o MRP automaticamente; essas etapas continuam separadas e governadas.

Interface: `/integrated-schedule/decision-cockpit/`. Documentação: `docs/MPS_DECISION_COCKPIT_090.md`.


## 0.9.1 — Ata formal e governança da decisão
A decisão do cockpit passa a ter ata, participantes, aprovações por área, riscos, condições, comentários e anexos. Veja `docs/MPS_DECISION_GOVERNANCE_091.md`.


## 0.9.2 — Matriz de alçadas e assinatura eletrônica
# MRP Django 0.9.2 — Matriz de alçadas e assinatura eletrônica

A 0.9.2 adiciona alçada automática por exposição financeira/serviço e assinatura eletrônica de aplicação com evidência criptográfica HMAC-SHA256. Não é assinatura digital qualificada ICP-Brasil e não substitui requisitos legais específicos.

## Critérios de alçada
- compras planejadas
- pico de capital de giro
- necessidade de financiamento não coberta
- risco prospectivo de serviço

## Níveis
Gerente, Diretor e Comitê Executivo. Regras configuram grupos Django e quantidade mínima de assinaturas.

## Assinatura
Usuários com senha local devem reautenticar a senha. Usuários SSO usam a sessão autenticada; ambos registram hash do conteúdo, HMAC, timestamp, usuário, grupos, IP e user-agent.


## 0.9.3 — Trilha de auditoria inviolável por encadeamento

Cockpit MPS com eventos encadeados por SHA-256, verificação de integridade e exportação de pacote de evidências. Consulte `docs/MPS_DECISION_AUDIT_093.md`.

## 0.9.4 — External audit anchors
A cadeia tamper-evident das decisões MPS pode ser ancorada em storage externo append-only/WORM. Consulte `docs/MPS_EXTERNAL_AUDIT_ANCHOR_094.md`.

## 0.9.5 — Automatic audit anchor policy

A 0.9.5 automatiza âncoras externas da trilha de decisão MPS. Cada planta pode exigir um ou mais providers, ancorar no congelamento e/ou diariamente e monitorar proteção em `/integrated-schedule/decision-integrity/`. Para redundância real, configure `MPS_AUDIT_ANCHOR_DIR` e `MPS_AUDIT_ANCHOR_SECONDARY_DIR` em storages independentes.

## 0.9.6 — Security & Compliance Center

A camada de governança MPS agora possui SLA de proteção por criticidade, incidentes de compliance, alertas por e-mail, exportação periódica de evidências, snapshots de indicadores e painel em `/integrated-schedule/security-compliance/`. Veja `docs/MPS_SECURITY_COMPLIANCE_096.md`.

## 0.9.7 — Compliance SLA & Escalation Engine

A versão 0.9.7 adiciona escalonamento automático para incidentes do Security & Compliance Center. Regras configuráveis promovem incidentes por tempo/severidade para equipe, gerente, diretor e executivo; notificações podem repetir com limite; contatos de plantão podem ser filtrados por dia/horário; e o dashboard apresenta MTTA/MTTR e escalonamentos ativos. Consulte `docs/MPS_COMPLIANCE_ESCALATION_097.md`.


## 0.9.8 — Corporate Compliance Escalation Calendar
Calendário corporativo de escalonamento, feriados, férias/ausências, substituições, múltiplos canais e métricas SLA por área/responsável. Consulte `docs/MPS_COMPLIANCE_ESCALATION_098.md`.


## 0.9.9 — Incident Command & Postmortem
Major incident, war room, timeline, CAPA, postmortem, 5 Whys e aprendizado incorporado às políticas do MRP.

## 1.0.0 — primeira release estável

A 1.0.0 consolida o fluxo ponta a ponta do projeto. Para homologar uma instalação use:

```bash
./scripts/release_validate.sh
```

Documentação operacional adicional:

- `docs/INSTALLATION_1_0.md`
- `docs/BACKUP_RESTORE_1_0.md`
- `docs/PRODUCTION_RUNBOOK_1_0.md`
- `docs/ACCEPTANCE_1_0.md`

Readiness manual:

```bash
python manage.py system_check
```

## 1.0.1 — hardening da release estável

A 1.0.1 melhora o processo de homologação sem alterar o domínio. Execute primeiro `./scripts/preflight.sh` e depois `./scripts/release_validate.sh`. O gate agora valida também drift de migrations, Redis real, readiness com retry e versão consistente entre `VERSION` e `settings.MRP_VERSION`.


## 1.0.2 — stable-line test hardening

A 1.0.2 corrige assertions antigas que prendiam a suíte a patches anteriores e adiciona `scripts/release_consistency.py` ao preflight, CI e gate de homologação. Não há alteração de schema ou funcionalidade de domínio.


## 1.0.3 — patch-agnostic stable release gate

A 1.0.3 elimina a recorrência de testes que prendem a suíte a um patch específico da linha 1.0.x. O gate `scripts/release_consistency.py` usa AST para rejeitar qualquer literal exato `1.0.N` dentro de assertions de `tests/test_release_*.py`. Não há nova migration ou mudança de domínio. Veja `docs/HARDENING_1_0_3.md`.

## 1.0.4 — Release gate diagnostics

A 1.0.4 mantém o domínio congelado e reforça a homologação: valida o contrato do Docker Compose antes do build, coleta `ps`/logs automaticamente em falhas e limpa o stack de teste por padrão. Use `RELEASE_KEEP_STACK=1` para preservar os containers quando precisar investigar uma falha.


## 1.0.5 — isolated release validation

The stable release gate now runs in a dedicated Docker Compose project with ephemeral host ports and clean disposable validation volumes. See `docs/HARDENING_1_0_5.md`. Normal development keeps the default host ports 5432/8000.

## 1.0.6 — gate sem bootstrap duplicado

A 1.0.6 torna a homologação mais determinística: comandos efêmeros de migrate/check/test/seed usam `SKIP_DJANGO_BOOTSTRAP=1`, enquanto o serviço web final continua validando o `entrypoint.sh` real. O novo `scripts/release_gate_lint.py` impede que chamadas cruas a `docker compose run --rm web` reintroduzam efeitos colaterais repetidos.

## 1.0.7 — Security deploy gate

A linha 1.0.x passa a executar `manage.py check --deploy --fail-level WARNING` em um perfil de produção dedicado durante a homologação. O smoke HTTP interno continua separado, evitando mascarar warnings de segurança com configurações de desenvolvimento. Consulte `docs/HARDENING_1_0_7.md`.


## 1.0.8 — PostgreSQL 18 persistence hardening

A linha estável passa a montar o volume do PostgreSQL 18 em `/var/lib/postgresql`, adiciona lint específico do contrato do Docker Official Image e uma prova de persistência que recria o container `db` durante a homologação. Antes de atualizar uma instalação 1.0.7 ou anterior, faça backup lógico do banco. Consulte `docs/HARDENING_1_0_8.md`.
