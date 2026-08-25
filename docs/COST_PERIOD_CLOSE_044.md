# MRP Django 0.4.4 — Fechamento industrial e auditoria

A versão 0.4.4 consolida o ciclo financeiro industrial: fechamento definitivo, validação do subledger, reconciliação físico x financeiro, estornos append-only e reabertura controlada.

## Fluxo de fechamento

`OPEN -> CLOSING -> CLOSED`

O endpoint `POST /api/accounting-periods/{id}/final-close/` gera inventário, WIP, reconciliação, variações, lançamentos e valida débito = crédito. Com `strict_reconciliation=true`, qualquer divergência físico x financeiro bloqueia o fechamento.

## Reabertura controlada

1. Solicitar em `POST /api/period-reopen-requests/request/`.
2. Aprovar ou rejeitar em `/approve/` ou `/reject/`.
3. Aplicar em `/apply/`.
4. A aplicação cria lançamentos inversos, preserva os originais e retorna o período para `OPEN`.

## Auditoria

`CostPeriodAudit` é append-only. Fechamento, falha, solicitação, decisão, reabertura e estornos também produzem `DomainEvent`.

## Relatório

`GET /api/accounting-periods/{id}/cost-report/` retorna estoque, WIP, variações, balanço do subledger, conciliação, fechamentos e reaberturas.
