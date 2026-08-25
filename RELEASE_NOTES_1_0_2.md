# MRP Django 1.0.2

Patch de hardening da linha estável 1.0.x.

## Corrigido

- Removida a assertion legada de `tests/test_release_100.py` que exigia exatamente `1.0.0` e quebraria a suíte nas releases posteriores.
- Generalizado o teste estático da 1.0.1 para preservar sincronização de versão sem bloquear patches futuros.
- Adicionado `scripts/release_consistency.py` para detectar divergência entre `VERSION` e `settings.MRP_VERSION`, assets operacionais ausentes e asserts obsoletos de patch version.
- Integrado o consistency gate ao preflight, release validation e CI.

## Schema

Nenhuma migration nova. A leaf de `integrated_scheduling` permanece `0040_mps_incident_command_postmortem_099`.
