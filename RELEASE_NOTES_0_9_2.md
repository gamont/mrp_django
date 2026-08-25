# MRP Django 0.9.2 — Matriz de alçadas e assinatura eletrônica

A 0.9.2 adiciona alçada automática por exposição financeira/serviço e assinatura eletrônica de aplicação com evidência criptográfica HMAC-SHA256. Não é assinatura digital qualificada ICP-Brasil e não substitui requisitos legais específicos.

## Critérios de alçada
- compras planejadas
- pico de capital de giro
- necessidade de financiamento não coberta
- risco prospectivo de serviço

## Níveis
Gerente, Diretor e Comitê Executivo. Regras configuram grupos Django e quantidade mínima de assinaturas.

## Assinatura
Usuários com senha local devem reautenticar a senha. Usuários SSO usam a sessão autenticada; ambos registram hash do conteúdo, HMAC, timestamp, usuário, grupos, IP e user-agent.
