# MRP 1.0.0 — Critério de aceite

A release 1.0.0 é uma consolidação funcional. O aceite deve ser executado no stack Docker real.

## Gate técnico obrigatório

```bash
./scripts/release_validate.sh
```

O gate precisa terminar com `RELEASE_1_0_0_VALIDATION_OK`.

## Fluxo funcional de homologação

1. Carregar `seed_demo` da fábrica SP01.
2. Executar MRP e confirmar planned orders MAKE/BUY.
3. Validar BOM, estoque, substituto e pegging.
4. Converter recomendações em compra/produção em ambiente de homologação.
5. Validar recebimento de compra e estoque.
6. Validar execução/encerramento de OP e rastreabilidade.
7. Executar RCCP/CTP e programação finita.
8. Validar OTIF e service level com entregas de teste.
9. Criar ciclo S&OP, publicar MPS operacional e executar MRP controlado.
10. Simular revisão MPS what-if/Pareto e decisão pelo cockpit.
11. Validar auditoria, assinatura, âncora externa e compliance.
12. Abrir/fechar Major Incident de teste e aprovar postmortem.

## Não conformidade

Qualquer falha de migration, `manage.py check --deploy`, `system_check`, pytest, Celery ping, readiness HTTP, integridade de ZIP ou restore de backup bloqueia a publicação de produção.
