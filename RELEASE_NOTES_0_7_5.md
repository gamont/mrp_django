# Release 0.7.5

## Comercial
- contatos comerciais por pedido;
- comunicação de promessa por e-mail/API/manual;
- log idempotente de comunicações;
- aceite, rejeição e contraproposta do cliente;
- caso comercial reaberto em rejeição/contraproposta;
- nova avaliação ATP/CTP opcional após rejeição;
- aceite do cliente integrado ao próximo MRP/ATP sem sobrescrever a data originalmente solicitada.

## Banco
Nova migração `0016_customer_confirmation_075.py`.

## Validação de geração
Compilação Python/AST e integridade do ZIP são verificadas no pacote. A suíte Django completa deve ser executada no Docker.
