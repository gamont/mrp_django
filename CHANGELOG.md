## 0.7.2
- Recovery Control Center
- RecoveryPolicy e RecoveryPlan
- severidade, ETA e impacto por trigger
- múltiplos planos CP-SAT
- auto-publicação opt-in para baixo risco
- interface, API, comando, migration e testes

# Changelog

## 0.7.1
- Recovery scheduling automático por eventos reais da fábrica.
- DowntimeEvent e LaborUnavailability alimentam ReschedulingTrigger quando afetam o cronograma oficial.
- Detector periódico de falta real de material via Celery Beat.
- Frozen horizon preservado durante o recovery CP-SAT.
- Comparação plano atual × plano recuperado e publicação controlada.


## 0.6.6
- Warm start do CP-SAT usando o melhor cenário heurístico disponível.
- Gap relativo configurável para término antecipado controlado.
- Celery + Redis para execuções assíncronas.
- Cancelamento cooperativo de runs.
- Histórico persistente de incumbents e progresso.
- Comparação CP-SAT × heurístico × publicado.
- Nova migração `0007_solver_async_warmstart_066.py`.


## 0.5.5 — OEE e monitoramento do chão de fábrica
- OEE diário por máquina: disponibilidade, performance e qualidade.
- MTBF e MTTR a partir de paradas não planejadas.
- Vínculo entre apontamento e máquina por `MachineProductionRecord`.
- Snapshot diário `OEEPeriodSnapshot`.
- Parâmetros `planned_minutes_per_day` e `ideal_cycle_seconds` na máquina.
- Painel Andon por planta com polling HTMX.
- Comando `calculate_oee`.
- Migração `shopfloor/0002_oee_monitoring`.

# 0.5.4

- Terminal touch/kiosk de chão de fábrica.
- Crachá + PIN hash para operador.
- Máquinas, estações e status em tempo real.
- Dispatch de operações por centro de trabalho.
- Setup, execução, pausa, apontamento e conclusão.
- Registro de paradas e motivos.
- HTMX com atualização a cada 10 segundos.

# Changelog

## 0.5.3 - 2026-08-07

- Edição operacional HTMX nas telas de detalhe.
- Controle de estado e apontamento por operação da OP.
- Baixa manual de material principal ou substituto reservado.
- Registro de inspeção por característica e amostra.
- Timeline atualizada após ações de produção e qualidade.
- Sem alterações de banco.


## 0.5.2 - 2026-08-07

- Telas de detalhe operacional e drill-down de MRP, produção, compras, qualidade e custos.
- Timeline documental e navegação contextual.
- Sem alterações de banco.

## 0.5.1 - 2026-08-07
- Ações HTMX transacionais nos painéis operacionais.
- Firmar/converter ordens planejadas.
- Liberar e apontar ordens de produção.
- Receber linhas de ordens de compra.
- Iniciar/finalizar inspeções de qualidade.
- Executar fechamento industrial pelo painel de custos.
- Feedback inline, fallback HTML e enforcement de permissões Django.

# 0.5.0

- Interface operacional Django + HTMX.
- Dashboards para planejamento, produção, compras, estoque, qualidade e custos.
- Login/logout, seletor de planta e atualização parcial automática.
- Testes da camada UI.

# Changelog

## 0.5.2 - 2026-08-07

- Telas de detalhe operacional e drill-down de MRP, produção, compras, qualidade e custos.
- Timeline documental e navegação contextual.
- Sem alterações de banco.

## 0.3.1
- Workflow ECO com análise, submissão, aprovação, rejeição e efetivação.
- Revisões de BOM e roteiros.
- Regras de efetividade.
- Análise de impacto em where-used, OPs abertas e ordens planejadas.
- Integração com DomainEvent e net-change MRP.
- API DRF, admin, migração e testes.

# Changelog

## 0.5.2 - 2026-08-07

- Telas de detalhe operacional e drill-down de MRP, produção, compras, qualidade e custos.
- Timeline documental e navegação contextual.
- Sem alterações de banco.

## 0.2.1 — Estabilização técnica

- Migrações iniciais versionadas para `common`, `masterdata`, `inventory`, `demand`, `production`, `purchasing` e `planning`.
- Constraints e índices explícitos para integridade e desempenho no PostgreSQL.
- Concorrência de estoque reforçada com bloqueio pessimista e ordem determinística de locks.
- Idempotência protegida contra retries e corridas simultâneas em estoque, recebimento de OC e apontamento de OP.
- Rejeição de chave de idempotência reutilizada com payload divergente.
- Perfis operacionais baseados em grupos e permissões nativas do Django.
- Política global de permissões DRF e regras específicas por ação.
- Logs estruturados em JSON e correlação por `X-Request-ID`.
- Endpoints de liveness, readiness e métricas Prometheus.
- Health check no Docker Compose e inicialização com Gunicorn.
- Pipeline de CI com PostgreSQL, compilação, lint, checks Django, migrações e testes.
- Testes adicionais de integridade, permissões, health checks e concorrência PostgreSQL.

## 0.2.0 — Incrementos MRP II

- CRP finito por centro, calendário e turno.
- ATP, CTP e cenários what-if com gargalos semanais.
- Recebimento de compra idempotente e fechamento automático da OC.
- Encerramento de OP com backflush, reservas e entrada do produto acabado.
- Substitutos de materiais com prioridade e equivalência.
- Mensagens de reschedule in/out.
- Net-change orientado a eventos e escopo de itens afetados.
- Auditoria append-only por eventos de domínio.
- Novos comandos, endpoints e testes.

## 0.3.2
- Controle de lotes, saldos e reservas por localização.
- Movimentações de lote idempotentes e protegidas por lock pessimista.
- Estados de lote: disponível, quarentena, inspeção, bloqueado, rejeitado, vencido e consumido.
- Números de série, histórico de movimentações e genealogia pai-componente.
- Consultas de genealogia e where-used pela API REST.
- Permissões operacionais para produção e almoxarifado.

## 0.3.3
- Módulo de qualidade com planos e características de inspeção.
- Ordens de inspeção de recebimento, produção e estoque.
- Resultados numéricos, booleanos e textuais por amostra.
- Aprovação total, parcial e rejeição com atualização automática do lote.
- Quarentena integrada à rastreabilidade.
- Não conformidades e decisões de uso, retrabalho, devolução, refugo ou seleção.
- Eventos de domínio, API DRF, Django Admin, migração e testes.

## 0.3.4 - 2026-08-06

- Novo módulo `apps.recall`.
- Investigação e execução de recall com genealogia multinível.
- Critérios de seleção por lote, série, item, fornecedor, período e origem.
- Bloqueio transacional de lotes e séries afetados.
- API DRF, migração, admin, documentação e testes.

## 0.4.0
- Versões de custo e workflow de aprovação/ativação.
- Taxas por centro de trabalho.
- Roll-up multinível de BOM e custos de roteiro.
- API, comando de gestão, migração e teste automatizado.


## 0.4.0
- Custo padrão versionado e roll-up multinível da BOM.
- Custo planejado e real por ordem de produção.
- Detalhamento por material, setup, mão de obra, máquina, overhead e refugo.
- Variações industriais e purchase price variance.
- APIs, migração, comando e testes.

## 0.5.6 - 2026-08-07

- OEE por turno com snapshots persistidos e suporte a turnos noturnos.
- Metas versionadas de OEE/A/P/Q por planta, centro ou máquina.
- Cálculo de perdas equivalentes de disponibilidade, performance e qualidade.
- Pareto de motivos de parada e dashboard histórico de melhoria contínua.
- Comando de reconstrução histórica e integração com o Andon.

## 0.6.5
- Solver CP-SAT (Google OR-Tools) para programação finita global.
- Precedências, máquinas alternativas, manutenção fixa, calendário e setup de sequência.
- Persistência de solver runs/assignments, API e CLI.

## 0.7.0
- Cronograma oficial versionado e horizonte congelado.
- Publicação de solução CP-SAT em slots operacionais.
- Planned × actual e desvios de execução.
- Gatilhos idempotentes e preparação de replanejamento por evento.

## 0.7.3
- Source-aware MRP demand pegging through BOM explosion.
- Exact recovery impact to SalesOrderLine/customer when 0.7.3 pegging is available.
- Promise current vs recovered, internal commercial alerts, and legacy inference labeling.

## 0.7.9
- Ciclo S&OP mensal formal/versionado.
- Demand Review com baseline forecast + pedidos e consenso ajustável.
- Supply Review agregado e registro de gaps.
- Registro de restrições, severidade, mitigação e decisões executivas.
- Aprovação bloqueada por restrições críticas abertas.
- Publicação em MPS e criação controlada de PlanningRun MRP.
- UI, API DRF, Admin, comandos, migração 0020 e testes.

## 0.8.0
- S&OP mensal → MPS semanal.
- Demand/Planning Time Fences.
- RCCP pré-publicação.
- Exceções de capacidade e bloqueio governado.
- Publicação MPS + PlanningRun + execução controlada do MRP.

## 0.8.1
- MPS semanal interativo, redistribuição entre buckets, delta versus baseline S&OP, RCCP reativo e aprovação de alterações na zona congelada.

## 0.8.4
- MRP what-if passa a gerar comparação financeira por revisão MPS.
- Custos MAKE por material/labor/machine/overhead, compras planejadas, estoque projetado, WIP e caixa como proxies claramente identificados.
- Cobertura de valoração, versão de custo e linhas financeiras por item/categoria.
- UI/API ampliadas e migração 0025.

## 0.8.5
- Budget financeiro por planta e buckets semanais/mensais.
- Condição de pagamento em fornecedor para temporização de compras.
- Cash-flow temporal baseline × revisão × budget.
- Estoque em valor ao longo do horizonte e variância para budget.
- API, Admin, comando, UI do relatório what-if, migrações e testes.

## 0.8.6
- Capital de giro projetado baseline × revisão com AR, AP, estoque e caixa acumulado.
- Condições de recebimento de clientes e parcelamento de clientes/fornecedores.
- Impostos/frete configuráveis como proxies de saída de caixa.
- Pico de NCG, DIO/DSO/DPO e Cash Conversion Cycle como indicadores gerenciais de planejamento.
- API, Admin, comando, UI e migrações 0005/0003/0027.

## 0.8.7
- Capacidade financeira e linhas de crédito integradas ao MPS what-if.
- Pico de draw, necessidade não coberta, crédito disponível e juros estimados por bucket.
- Política opcional de bloqueio de aprovação quando a revisão excede o crédito utilizável.
- API, Admin, comando, UI e migração 0028.

## 0.8.8
- Otimizador heurístico multicritério para revisão MPS.
- Candidatos de shift later/earlier, level load e supplier terms.
- `planning_overrides` no MRP what-if para MPS inline e sourcing alternativo.
- Ranking por MRP/RCCP/working-capital/financing/custos.
- Adoção explícita de candidato como nova revisão DRAFT.
- API, Celery, CLI, UI, testes e documentação.

## 0.8.9
- CP-SAT Pareto optimizer for MPS revisions; full what-if evaluation and non-dominated frontier.


## 0.9.0
- Cockpit executivo para runs CP-SAT Pareto concluídos.
- Gráfico interativo e comparação lado a lado dos cenários.
- Shortlist, justificativa e aprovação executiva segregada.
- Congelamento controlado do cenário escolhido como revisão oficial APPROVED.
- Snapshot de auditoria, API, UI, comando e migração 0031.


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


## 0.9.3
- Trilha de auditoria SHA-256 encadeada e pacote ZIP de evidências para decisões MPS.

## 0.9.4
- External audit anchor for MPS decision chain, external receipt verification, evidence integration.

## 0.9.5
- Política automática de âncoras por planta, dupla âncora independente, Celery Beat diário e painel de integridade/proteção.

## 0.9.6
- Security & Compliance Center para decisões MPS.
- SLA por criticidade, incidentes, alertas, evidências periódicas e KPIs.

## 0.9.7
- Compliance SLA & Escalation Engine com níveis TEAM/MANAGER/DIRECTOR/EXECUTIVE.
- Regras temporais por severidade/categoria, repetição controlada e contatos de plantão.
- Métricas MTTA/MTTR, API, dashboard, Celery Beat e comandos operacionais.

## 0.9.8
- Corporate escalation calendar: holidays, absences and substitutions.
- Multi-channel escalation delivery (EMAIL/API/Teams/Slack) with delivery log.
- Acknowledged-but-unresolved escalation clock and SLA metrics by area/responsible.


## 0.9.9 — Incident Command & Postmortem
Major incident, war room, timeline, CAPA, postmortem, 5 Whys e aprendizado incorporado às políticas do MRP.

## 1.0.0
- Release de consolidação e estabilização do MRP/MRP II.
- Readiness command `system_check`.
- Gate Docker `scripts/release_validate.sh`.
- Backup/restore PostgreSQL com SHA-256.
- Runbook, instalação e roteiro de aceite 1.0.
- Sem alteração de schema de domínio nesta release.

## 1.0.1
- Hardening do `system_check` e remoção de versão hard-coded.
- `REDIS_URL` separado do broker Celery.
- Preflight e lint estático do grafo de migrations.
- Release gate com retries e verificação de drift de migrations.
- CI com Redis e readiness consolidado.


## 1.0.2
- Corrige testes legados que fixavam a versão 1.0.0/1.0.1.
- Adiciona release consistency gate ao preflight, CI e homologação.
- Sem migration nova.


## 1.0.3
- Corrige o pin exato da versão 1.0.2 no teste estático de release.
- `release_consistency.py` agora detecta via AST qualquer assertion que fixe um patch `1.0.x`.
- Adiciona teste de regressão patch-agnostic e documentação de hardening.
- Sem migration nova e sem alteração funcional de domínio.

## 1.0.4
- Hardening do release gate: compose contract lint, diagnóstico automático e cleanup seguro em falhas.
- Sem novas migrations ou funcionalidades de domínio.


## 1.0.5
- Isolated Docker Compose project for release validation.
- Ephemeral host ports in the release gate to avoid collisions with dev stacks.
- Clean validation volumes removed by default after each run.
- Compose lint guards release-port parameterization.
- No domain migrations.

## 1.0.6
- Hardening do release gate: one-off web commands ignoram bootstrap implícito repetido.
- Novo release_gate_lint integrado ao preflight/CI.

## 1.0.7
- Gate `check --deploy` estrito com perfil de produção efêmero.
- Novo lint estático do perfil de segurança.
- Sem migrations ou mudanças funcionais de domínio.


## 1.0.8
- Corrige o alvo do volume nomeado para PostgreSQL 18: `/var/lib/postgresql`.
- Adiciona lint estático e prova de persistência por recriação do container no release gate.
- Hardening do restore para ignorar bootstrap implícito em comandos one-off.
- Sem migrations ou mudanças funcionais de domínio.
