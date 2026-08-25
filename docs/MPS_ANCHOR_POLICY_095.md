# MPS 0.9.5 — política automática de âncoras e painel de proteção

A 0.9.5 automatiza a proteção externa da trilha de auditoria introduzida em 0.9.3/0.9.4.

## Política por planta
`MPSDecisionAnchorPolicy` define cadência (`ON_FREEZE`, `DAILY`, `BOTH`), providers exigidos, idade máxima da âncora, retenção administrativa e verificação após publicação.

## Providers independentes
- `FILE_APPEND_ONLY`: diretório primário (`MPS_AUDIT_ANCHOR_DIR`).
- `FILE_SECONDARY`: diretório secundário (`MPS_AUDIT_ANCHOR_SECONDARY_DIR`).
- `MANUAL_EXTERNAL`: referência externa registrada manualmente; não é publicada automaticamente.

Para independência real, os diretórios primário e secundário devem apontar para storages separados. Dois diretórios no mesmo disco não equivalem a duas âncoras independentes.

## Automação
Ao congelar um cockpit, políticas `ON_FREEZE`/`BOTH` publicam as âncoras após o commit da transação. O Celery Beat executa diariamente `integrated_scheduling.run_mps_anchor_policy` para políticas `DAILY`/`BOTH`.

## Estados do painel
- `PROTECTED`: cadeia íntegra e todos os providers requeridos dentro da idade máxima.
- `STALE`: âncora existe, mas excedeu a idade máxima.
- `UNPROTECTED`: provider obrigatório sem âncora.
- `MISMATCH`: cadeia ou âncora diverge.

A política de retenção é informativa nesta versão: a aplicação não apaga automaticamente recibos imutáveis. A retenção efetiva deve ser configurada no storage externo/WORM.
