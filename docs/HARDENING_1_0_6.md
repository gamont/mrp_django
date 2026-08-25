# Hardening 1.0.6 — one-off commands sem bootstrap duplicado

## Problema corrigido

O container `web` usa `entrypoint.sh`. Por padrão, antes de executar o comando solicitado, o entrypoint roda:

1. `manage.py check --deploy --fail-level ERROR`;
2. `manage.py migrate --noinput`;
3. `manage.py bootstrap_roles`;
4. `manage.py collectstatic --noinput`.

Na 1.0.5, cada `docker compose run --rm web ...` do gate de homologação disparava esse bootstrap completo e, em seguida, executava novamente o comando pedido. Assim um único gate podia migrar, sincronizar papéis e coletar estáticos diversas vezes antes dos testes.

## Correção 1.0.6

O `release_validate.sh` agora centraliza comandos efêmeros em `run_web`, que injeta:

```bash
SKIP_DJANGO_BOOTSTRAP=1
```

Migrations, checks, testes e seed passam a executar somente a operação explicitamente solicitada.

O container `web` de longa duração continua sendo iniciado normalmente, sem `SKIP_DJANGO_BOOTSTRAP`. Portanto o gate ainda valida o comportamento real do entrypoint de produção, porém uma única vez na inicialização da aplicação.

## Proteção contra regressão

`scripts/release_gate_lint.py` verifica estaticamente que:

- o helper `run_web` existe;
- ele usa `SKIP_DJANGO_BOOTSTRAP=1`;
- não reaparecem chamadas cruas `docker compose run --rm web` no gate;
- migrate/check/system_check/pytest/seed passam pelo helper;
- o serviço web final ainda sobe normalmente.

O lint faz parte do `preflight.sh` e do CI.
