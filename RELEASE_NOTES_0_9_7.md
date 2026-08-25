# Release 0.9.7 — Compliance SLA & Escalation Engine

## Novidades
- Escalonamento temporal TEAM / MANAGER / DIRECTOR / EXECUTIVE.
- Regras por severidade, categoria e minutos desde a detecção.
- Repetição de alertas com intervalo e limite persistentes.
- Plantão por dia da semana, horário e nível de escalonamento.
- Métricas MTTA/MTTR para incidentes de compliance.
- Celery Beat a cada 15 minutos.
- API, Admin, dashboard e comandos de seed/execução.

## Migração
`0038_mps_compliance_escalation_097.py`

## Upgrade
```bash
docker compose build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py seed_mps_compliance_escalation --plant SP01
docker compose run --rm web python manage.py check
docker compose run --rm web pytest
docker compose up -d
```
