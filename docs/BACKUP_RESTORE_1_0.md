# MRP 1.0.0 — Backup e restore

## Backup PostgreSQL

```bash
./scripts/backup.sh
```

O backup usa `pg_dump --format=custom` dentro do container PostgreSQL e cria um arquivo `.sha256` ao lado do dump.

## Restore

```bash
./scripts/restore.sh backups/mrp_YYYYMMDD_HHMMSS.dump
```

O restore é destrutivo e exige confirmação literal `RESTORE`. Após restaurar, executa migrations e `manage.py check`.

## Política recomendada

- Backup diário e antes de cada upgrade.
- Retenção em storage externo ao host da aplicação.
- Criptografia do storage/backup conforme a política da empresa.
- Teste de restauração periódico em ambiente isolado.
- Para âncoras/auditoria 0.9.x, preservar também os storages externos usados por `MPS_AUDIT_ANCHOR_DIR` e `MPS_AUDIT_ANCHOR_SECONDARY_DIR`.
