# MRP Django 0.5.0

## Interface operacional Django + HTMX

- Novo app `apps.ui`.
- Login/logout por sessão Django.
- Seletor de planta persistido em sessão.
- Layout administrativo responsivo com sidebar.
- Painel do planejador: MRP, exceções, ordens e gargalos.
- Painel de produção: OPs, atrasos e operações ativas.
- Painel de compras: OCs, linhas abertas e atrasos.
- Painel de estoque: saldos, alocações e faltas.
- Painel de qualidade: inspeções e não conformidades.
- Painel de custos: período, WIP, ItemCost e variações.
- Atualização parcial HTMX a cada 60 segundos.
- Fallback server-side sem dependência obrigatória de HTMX.
- CSS responsivo local em `apps/ui/static/ui/app.css`.
- Testes de autenticação, seleção de planta e resposta parcial HTMX.
