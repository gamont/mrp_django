# Engenharia e ECO

A ECO registra motivo, itens afetados, ação, valores anteriores/novos, aprovações e regra de efetividade. A análise de impacto identifica where-used, OPs abertas e ordens planejadas. Revisões liberadas preservam histórico e permitem reconstruir a configuração aprovada.

## Segurança
Aprovação requer `engineering.approve_engineeringchange`; efetivação requer `engineering.activate_engineeringchange`.

## Efetividade
A versão implementa validação e armazenamento de data, lote, série, quantidade, esgotamento de estoque e dependência de outra ECO. A aplicação automática da BOM está habilitada para imediata/data; os demais gatilhos ficam preparados para integração com lotes e séries na 0.3.2.
