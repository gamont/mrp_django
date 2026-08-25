# Release 1.0.6

Release de manutenção da linha estável 1.0.x, sem alteração de domínio e sem migration nova.

## Correções

- elimina bootstrap implícito repetido nos comandos efêmeros do `release_validate.sh`;
- adiciona helper `run_web` com `SKIP_DJANGO_BOOTSTRAP=1`;
- mantém o bootstrap real do `entrypoint.sh` na inicialização final do serviço web;
- adiciona `scripts/release_gate_lint.py` para impedir regressão;
- integra o novo lint ao preflight e ao GitHub Actions;
- atualiza `VERSION` e `MRP_VERSION` para 1.0.6.

## Motivação

Antes, comandos como `docker compose run --rm web python manage.py check` acionavam primeiro o entrypoint, que já executava check, migrate, bootstrap de papéis e collectstatic. Isso aumentava tempo, adicionava efeitos colaterais e tornava a sequência de homologação menos determinística.
