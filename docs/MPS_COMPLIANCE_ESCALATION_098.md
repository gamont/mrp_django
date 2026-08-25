# MPS Compliance Escalation 0.9.8

A versão 0.9.8 amplia o motor de escalonamento com calendário corporativo, feriados, ausências, substituições temporárias, canais EMAIL/API/Teams/Slack, regras com relógio após reconhecimento e métricas por área/responsável.

## Regras de relógio
- `FIRST_SEEN`: limiar contado desde a abertura.
- `ACKNOWLEDGED`: limiar contado desde `acknowledged_at`; permite escalar incidentes reconhecidos mas ainda não resolvidos.

## Plantão
Um contato ausente não recebe acionamento. Uma substituição vigente pode assumir seu nível. Em feriado corporativo apenas contatos com `include_holidays=True` participam do plantão.

## Canais
E-mail usa o backend Django. API/Teams/Slack usam POST JSON para endpoints explicitamente cadastrados. Falhas ficam em `MPSComplianceNotificationDelivery`; não são escondidas.

## Segurança
Webhooks são segredos operacionais e devem ser protegidos por controles de acesso/configuração. A 0.9.8 não implementa um cofre de segredos.
