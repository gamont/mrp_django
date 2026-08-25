# Hardening 1.0.8 — PostgreSQL 18 persistence

A 1.0.8 corrige o alvo do volume persistente do serviço `db` para o contrato do Docker Official Image PostgreSQL 18.

## Mudança principal

O Compose anterior montava o volume nomeado em:

```text
/var/lib/postgresql/data
```

A imagem oficial PostgreSQL 18 usa `PGDATA=/var/lib/postgresql/18/docker` e declara o volume em:

```text
/var/lib/postgresql
```

Por isso a 1.0.8 passa a usar:

```yaml
volumes:
  - postgres_data:/var/lib/postgresql
```

## Upgrade de uma instalação 1.0.7 ou anterior

Antes de trocar a configuração do volume, faça um backup lógico enquanto o container atual ainda está operacional:

```bash
./scripts/backup.sh
```

Depois implante a 1.0.8 em ambiente controlado. Para uma instalação já existente, trate a mudança de layout do PostgreSQL como uma migração de storage: não presuma que dados de um volume criado com o alvo antigo serão automaticamente reutilizados.

Em homologação limpa, `release_validate.sh` cria um registro de prova, recria o container `db` e confirma que o registro sobreviveu antes de executar as migrations.

## Novo lint

```bash
python scripts/postgres_volume_lint.py
```

Ele bloqueia o retorno acidental ao alvo legado enquanto `docker-compose.yml` usar PostgreSQL 18+.

## Restore

Os comandos Django one-off de `scripts/restore.sh` agora usam `SKIP_DJANGO_BOOTSTRAP=1`, evitando executar novamente o bootstrap completo do entrypoint durante `migrate` e `check`.
