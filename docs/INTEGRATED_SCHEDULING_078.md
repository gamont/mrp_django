# 0.7.8 — S&OP / Executive Service Dashboard

Consolida OTIF, forecast accuracy (WAPE), backlog, estoque, OEE e utilização de capacidade em snapshot mensal por planta. Inclui cenários what-if agregados de demanda/capacidade/estoque. O cenário executivo não substitui a execução detalhada de MRP ou CP-SAT.

## Receita em risco
`SalesOrderLine.unit_net_price` é opcional. `revenue_at_risk` considera somente linhas precificadas e `revenue_coverage_pct` explicita a cobertura, evitando tratar preço ausente como receita conhecida igual a zero.
