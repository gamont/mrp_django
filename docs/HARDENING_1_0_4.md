# Hardening 1.0.4

A 1.0.4 reforça o gate de homologação, especialmente diagnóstico e limpeza quando uma etapa Docker falha.

## Pré-flight

```bash
./scripts/preflight.sh
```

Além dos checks da 1.0.3, agora valida o compose em duas camadas:

```bash
docker compose config --quiet
python scripts/compose_lint.py
```

## Homologação

```bash
./scripts/release_validate.sh
```

Em falha, o script captura estado e os últimos logs de `db`, `redis`, `web`, `worker` e `beat`, e depois derruba o stack.

Para preservar os containers após uma falha:

```bash
RELEASE_KEEP_STACK=1 ./scripts/release_validate.sh
```

Para aumentar a quantidade de linhas de log capturadas:

```bash
RELEASE_LOG_TAIL=300 ./scripts/release_validate.sh
```

Isso é indicado para investigação de erros de migration, readiness ou Celery.
