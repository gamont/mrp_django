# Programação integrada 0.6.3 — sequência finita avançada

## Objetivo

A 0.6.3 acrescenta ao scheduler finito um custo de troca dependente da sequência. Em vez de considerar que toda operação tem sempre o mesmo setup, o motor consulta a família do item anterior e a família do próximo item no recurso escolhido.

## Cadastro

1. Cadastre `ProductFamily` por planta.
2. Associe itens usando `ItemSchedulingProfile`.
3. Cadastre `SequenceSetupRule` para o par origem/destino. Uma regra específica de máquina tem precedência sobre a regra genérica do centro.
4. Escolha a regra de despacho no cenário.

Exemplo:

```
A → A = 0.25 h
A → B = 2.00 h
B → A = 1.50 h
B → B = 0.20 h
```

Se a máquina termina uma operação da família A e a próxima pertence à família B, 2 horas adicionais são consumidas como capacidade antes da nova operação.

## Dispatching

`EDD`, `SPT`, `CR`, `PRIORITY` e `SETUP_MIN` são suportados. O modo de campanha pode agrupar `campaign_code` (ou família quando a campanha estiver vazia) e manter a regra de despacho dentro do agrupamento.

## Integração com calendário

O setup dependente da sequência é somado às horas requeridas e consumido dentro das janelas válidas da 0.6.2. Assim, pausas, feriados, horas extras e fechamentos continuam válidos também para o setup.

## Limitação conhecida

O primeiro passo da 0.6.3 usa heurísticas de despacho e uma função de score, não um solver matemático global. Isso torna a simulação determinística e operacionalmente explicável, mas não garante ótimo global em problemas grandes de job-shop.
