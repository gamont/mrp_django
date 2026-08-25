# 0.7.2 — Recovery Control Center

Centraliza rupturas em uma fila operacional, calcula severidade/ETA/impacto, gera múltiplos recovery plans com estratégias CP-SAT diferentes, ranqueia por risco e permite auto-publicação apenas quando a política da planta estiver explicitamente habilitada e todos os limites forem atendidos.

## Governança
A auto-publicação nasce desativada. Os limites incluem risco, operações movidas/atrasadas, trocas de máquina, pedidos impactados e atraso máximo.

## Impacto comercial
Como WorkOrder não possui vínculo contratual direto com SalesOrder, o 0.7.2 apresenta impacto comercial inferido por item e data solicitada. Para decisão comercial exata, a instalação deve usar/estender o pegging do MRP até SalesOrderLine.
