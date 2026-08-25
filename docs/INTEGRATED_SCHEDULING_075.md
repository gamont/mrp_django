# 0.7.5 — Confirmação comercial e comunicação ao cliente

A versão 0.7.5 completa o ciclo comercial iniciado na 0.7.4. Uma promessa aprovada internamente pode ser comunicada por e-mail, API ou fluxo manual; a resposta do cliente é preservada em histórico e o aceite passa a ser a data efetiva usada pelo próximo MRP/ATP.

## Governança

- `requested_date` continua sendo a data originalmente solicitada pelo cliente e não é sobrescrita.
- `SalesOrderPromise` representa a proposta/aprovação interna.
- `CustomerPromiseResponse` representa a decisão do cliente.
- Somente resposta `ACCEPTED` define a data efetiva de compromisso para o próximo planejamento.
- Rejeição/contraproposta reabre o caso comercial e pode gerar nova avaliação ATP/CTP.
- Toda saída é registrada em `CommercialCommunication` com chave idempotente.

## Comunicação

Em desenvolvimento o backend padrão de e-mail é o console. Em produção configure `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL` e as credenciais do provedor SMTP. O canal API faz POST JSON na URL cadastrada no contato e envia `Idempotency-Key`.

## Integração MRP/ATP

MRP e ATP consultam `effective_customer_commitment_date()`. Quando existe aceite, usam `confirmed_date`; caso contrário mantêm `SalesOrderLine.requested_date`.
