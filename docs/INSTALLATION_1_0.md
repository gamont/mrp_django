# MRP 1.0.0 — Instalação de produção

## Pré-requisitos

- Docker Engine + Docker Compose v2.
- Host Linux com armazenamento persistente para PostgreSQL e Redis.
- Proxy TLS (nginx, Traefik ou equivalente) em produção.
- Segredos e credenciais fora do repositório.

## Primeira instalação

```bash
cp .env.example .env
# ajuste DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS e senhas

docker compose build
docker compose up -d db redis
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py bootstrap_roles
docker compose run --rm web python manage.py collectstatic --noinput
docker compose up -d
```

## Validação da release

```bash
./scripts/release_validate.sh
```

Esse script executa build, migrations, roles, `check --deploy`, `system_check`, pytest, seed da fábrica de faróis, ping do Celery e health/readiness HTTP.

## Dados de demonstração

```bash
docker compose run --rm web python manage.py seed_demo
```

O seed é idempotente e cria a planta SP01, farol H7, conjunto óptico, componentes, BOM, fornecedores, estoques, centros de trabalho, turnos, roteiros e MPS demonstrativo.

## Produção

Recomendado configurar `DJANGO_DEBUG=0`, `DJANGO_SECURE_SSL_REDIRECT=1`, cookies seguros, HSTS após confirmar HTTPS e `DJANGO_ALLOWED_HOSTS` explícito. Nunca use `DJANGO_SECRET_KEY=dev-only-secret-key`.
