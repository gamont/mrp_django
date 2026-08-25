# Hardening 1.0.7 — production-profile security gate

## Problema corrigido

O gate 1.0.6 executava `python manage.py check --deploy` herdando o `.env` de desenvolvimento. Com valores como `DJANGO_DEBUG=1`, cookies não seguros e HSTS desativado, o comando emitia warnings, mas a release não os tratava como falha. Isso permitia que o gate declarasse sucesso sem provar que um perfil de produção passava nos checks de segurança do Django.

## Solução

A 1.0.7 separa dois perfis durante a homologação:

1. **perfil estrito de segurança** — usado apenas para `check --deploy --fail-level WARNING`, com DEBUG desligado, HTTPS redirect, cookies seguros, HSTS e chave dedicada do gate;
2. **perfil de smoke interno** — mantém HTTP dentro da rede Compose para health checks e Celery, sem confundir a validação de segurança com a conectividade do container.

O helper `run_web_secure` aplica as variáveis apenas ao comando efêmero. Nenhum segredo de produção é embutido no projeto; `RELEASE_DJANGO_SECRET_KEY` é um segredo exclusivo do gate e pode ser sobrescrito por CI/ops.

## Validação

Execute:

```bash
./scripts/preflight.sh
./scripts/release_validate.sh
```

O preflight agora inclui `security_profile_lint.py`, que impede remoções acidentais das proteções mínimas da checagem de deploy.
