# MRP Django 0.5.1

Release operacional HTMX sobre a 0.5.0.

## Ações adicionadas aos painéis

- Planejamento: firmar e converter ordem planejada.
- Produção: liberar OP com reserva de materiais e apontar produção com backflush.
- Compras: receber linha de OC com entrada de estoque, lote e idempotência.
- Qualidade: iniciar e concluir inspeção.
- Custos: fechamento industrial definitivo com opção de reconciliação estrita.

Todas as ações usam os serviços de domínio existentes, preservando transações, locks, validações, auditoria e idempotência já implementados no backend.

## Segurança

As ações exigem autenticação por sessão e permissões Django do respectivo domínio. O frontend oculta ações para usuários sem permissão e as views também as validam no servidor.

## HTMX

As operações atualizam somente `#dashboard-content`, exibindo sucesso ou erro de validação no próprio painel. O fallback HTML tradicional continua disponível quando a requisição não é HTMX.
