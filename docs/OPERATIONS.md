# Operação e observabilidade — MRP 0.2.1

## Inicialização

O container web executa, nesta ordem:

1. `python manage.py check --deploy --fail-level ERROR`
2. `python manage.py migrate --noinput`
3. `python manage.py bootstrap_roles`
4. `python manage.py collectstatic --noinput`
5. Gunicorn

A inicialização falha quando existe erro de configuração, migração inválida ou indisponibilidade do banco.

## Health checks

### Liveness

```http
GET /health/live/
```

Verifica apenas se o processo Django está respondendo. Não consulta o banco.

### Readiness

```http
GET /health/ready/
```

Retorna `200` somente quando:

- o banco responde a `SELECT 1`;
- não existem migrações pendentes.

Quando uma verificação falha, retorna `503` com o detalhe em `checks`.

## Métricas

```http
GET /metrics/
```

As métricas incluem:

- total de requisições por método, rota e status;
- duração acumulada por método e rota;
- indicação de disponibilidade do banco.

Para proteger o endpoint, configure:

```env
MRP_METRICS_TOKEN=um-token-longo
```

E envie:

```http
X-Metrics-Token: um-token-longo
```

As métricas são mantidas em memória por processo. Em múltiplos workers, o coletor deve consultar cada worker ou a aplicação deve migrar posteriormente para um backend multiprocess apropriado.

## Logs estruturados

Cada requisição gera um registro JSON contendo:

- `timestamp`;
- `level`;
- `logger`;
- `message`;
- `request_id`;
- método, rota e caminho;
- status HTTP;
- duração em milissegundos;
- usuário autenticado, quando aplicável;
- endereço remoto.

O cliente pode enviar `X-Request-ID`; caso não envie, o middleware gera um identificador. O mesmo valor é devolvido na resposta.

Variáveis úteis:

```env
DJANGO_LOG_LEVEL=INFO
DJANGO_DB_LOG_LEVEL=WARNING
POSTGRES_STATEMENT_TIMEOUT_MS=30000
POSTGRES_CONN_MAX_AGE=60
```

## Segurança atrás de proxy

Em produção com TLS terminado no proxy:

```env
DJANGO_TRUST_PROXY=1
DJANGO_SECURE_SSL_REDIRECT=1
DJANGO_SESSION_COOKIE_SECURE=1
DJANGO_CSRF_COOKIE_SECURE=1
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_PRELOAD=1
```

Configure `DJANGO_ALLOWED_HOSTS` com nomes explícitos. Não use `*` em produção.

## Atualização da versão 0.2

A versão 0.2 não distribuía arquivos iniciais de migração. Para um banco já criado por `makemigrations` local:

1. pare gravações;
2. faça backup lógico e físico;
3. compare tabelas, constraints e índices com as migrações 0.2.1;
4. valide primeiro em staging;
5. use `migrate --fake-initial` somente quando o esquema inicial for compatível;
6. aplique diferenças restantes por migrações de ajuste controladas.

Para uma instalação nova, execute `migrate` normalmente.

## Comandos de diagnóstico

```bash
python manage.py check
python manage.py showmigrations
python manage.py migrate --plan
python manage.py makemigrations --check --dry-run
python manage.py bootstrap_roles
pytest
coverage run -m pytest && coverage report
```
