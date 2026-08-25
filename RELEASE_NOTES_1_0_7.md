# Release 1.0.7

Release de manutenção da linha estável 1.0.x.

- `check --deploy` passa a rodar em perfil de produção dedicado e com `--fail-level WARNING`.
- Novo helper `run_web_secure` evita validar segurança usando o `.env` de desenvolvimento.
- Novo `scripts/security_profile_lint.py` protege o contrato do gate.
- `preflight.sh` e CI incorporam o novo lint.
- Sem novas funcionalidades de domínio e sem migrations novas.
