# MRP 1.0.0 — Production Runbook

## Health

- `/health/live/`: processo web vivo.
- `/health/ready/`: dependências necessárias prontas.
- `python manage.py system_check`: Django + DB + Redis + OR-Tools + Celery import + versão.

## Subida

```bash
docker compose up -d
docker compose ps
```

## Logs

```bash
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f beat
```

## Antes de upgrade

```bash
./scripts/backup.sh
docker compose run --rm web python manage.py check
```

## Upgrade

```bash
docker compose build
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py bootstrap_roles
docker compose run --rm web python manage.py check --deploy
docker compose run --rm web pytest -q
docker compose up -d
```

## Rollback de aplicação

Reimplante a imagem/revisão anterior. Se o release tiver migration não reversível, restaure o backup validado em ambiente controlado em vez de tentar apagar dados manualmente.
