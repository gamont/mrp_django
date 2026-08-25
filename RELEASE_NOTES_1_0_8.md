# Release 1.0.8

Release de hardening da linha estável 1.0.x, sem migrations de domínio.

## Correções

- Corrige o volume persistente do PostgreSQL 18 de `/var/lib/postgresql/data` para `/var/lib/postgresql`.
- Adiciona `scripts/postgres_volume_lint.py` ao preflight e CI.
- Adiciona prova de persistência no `release_validate.sh`: grava token, recria o container PostgreSQL e exige que o token sobreviva.
- Corrige `scripts/restore.sh` para executar comandos Django one-off com `SKIP_DJANGO_BOOTSTRAP=1`.
- Atualiza documentação de upgrade/backup para instalações anteriores.

## Compatibilidade

Não há migration nova. A última migration de domínio permanece `0040_mps_incident_command_postmortem_099.py`.
