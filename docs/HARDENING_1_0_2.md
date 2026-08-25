# Hardening 1.0.2

A 1.0.2 corrige uma regressão de homologação da linha estável: o teste legado da 1.0.0 ainda exigia exatamente `1.0.0`, o que tornaria qualquer patch 1.0.x posterior incompatível com a própria suíte completa.

## Mudanças

- testes históricos da 1.0 passam a validar a linha estável e a sincronização de versão, sem fixar patch antigo;
- `scripts/release_consistency.py` valida `VERSION` x `settings.MRP_VERSION`, assets operacionais e assertions antigas de versão;
- o consistency gate roda no preflight, no release gate e no CI;
- nenhuma migration ou alteração funcional de domínio foi adicionada.

## Homologação

```bash
./scripts/preflight.sh
./scripts/release_validate.sh
```

Antes de publicar um novo patch 1.0.x, `python scripts/release_consistency.py` deve terminar com `RELEASE_CONSISTENCY_OK`.
