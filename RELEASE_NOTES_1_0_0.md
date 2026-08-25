# MRP 1.0.0 — Release Notes

A 1.0.0 consolida a linha 0.x como primeira release estável operacional do projeto.

## Entregas de estabilização

- Novo `python manage.py system_check` para readiness de aplicação, banco, Redis, OR-Tools, Celery e versão.
- `scripts/release_validate.sh` como gate repetível de homologação em Docker.
- Procedimentos de backup/restore PostgreSQL com checksum SHA-256.
- Runbook de produção, instalação e critério de aceite.
- Smoke script do MRP com seed idempotente da fábrica de faróis.
- Versão pública/API atualizada para 1.0.0.
- Nenhuma nova tabela de domínio na 1.0.0: a release prioriza estabilização do schema existente.

## Escopo consolidado

S&OP, MPS semanal/time fences, MRP/netting/pegging, ATP/CTP, CRP/RCCP, programação finita CP-SAT, manutenção, shopfloor/OEE, qualidade, rastreabilidade/recall, costing, OTIF, what-if financeiro, capital de giro, otimização Pareto, cockpit executivo, governança, auditoria, compliance e incident command/postmortem.

## Validação obrigatória

Execute `./scripts/release_validate.sh` no stack Docker alvo antes de produção. O pacote gerado fora do Docker passa por validação estática, mas o aceite funcional exige PostgreSQL/Redis/Celery/OR-Tools no ambiente real.
