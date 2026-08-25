# 0.7.6 — OTIF e nível de serviço

A versão 0.7.6 registra entregas comerciais reais e calcula On-Time, In-Full e OTIF por linha de pedido. A referência pode ser a data originalmente solicitada, a promessa aprovada ou a data aceita pelo cliente. A data solicitada nunca é sobrescrita.

## Fórmulas
- On-Time: entrega completa até a data de referência.
- In-Full: quantidade acumulada entregue >= quantidade pedida.
- OTIF: On-Time AND In-Full.

Entregas parciais são acumuladas; `full_delivery_date` é a primeira data em que a soma entregue alcança a quantidade pedida.

## Causas
O sistema tenta associar evidências de recovery/desvios a MATERIAL, MACHINE, LABOR, CAPACITY etc. Quando não existe evidência suficiente, registra UNKNOWN; não inventa causa.
