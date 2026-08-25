# MRP 1.0.1 — Hardening e homologação

A 1.0.1 é uma release de manutenção. Ela não altera o modelo de domínio nem cria novas migrations. O objetivo é tornar a homologação reproduzível e reduzir falsos positivos no readiness check.

## Mudanças principais

- `system_check` deixou de conter a versão `1.0.0` hard-coded e compara `settings.MRP_VERSION` com o arquivo `VERSION`.
- Redis agora possui `REDIS_URL` próprio. Isso evita assumir que o broker do Celery é necessariamente Redis.
- parsing de hostname usa `urllib.parse.urlparse`, funcionando corretamente com credenciais/portas em URLs.
- `scripts/migration_lint.py` faz uma validação estática, sem Django, de dependências locais e múltiplas folhas de migration.
- `scripts/preflight.sh` valida Docker, Docker Compose, `.env`, versão e grafo de migrations antes do gate completo.
- `release_validate.sh` ganhou espera com retry para PostgreSQL, Redis, web e Celery; também executa `makemigrations --check --dry-run`.
- CI ganhou Redis real, `migration_lint.py` e `manage.py system_check`.

## Homologação recomendada

```bash
cp .env.example .env
# ajustar DJANGO_SECRET_KEY, ALLOWED_HOSTS e parâmetros de produção
./scripts/preflight.sh
./scripts/release_validate.sh
```

O sucesso final esperado é `RELEASE_1_0_1_VALIDATION_OK`.

## Sem migration nova

A última migration de domínio continua sendo `0040_mps_incident_command_postmortem_099.py`. A 1.0.1 altera somente código operacional, checks, CI, documentação e testes de release.
