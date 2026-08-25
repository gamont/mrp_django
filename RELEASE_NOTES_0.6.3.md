# Release 0.6.3 — Sequência finita avançada

A versão 0.6.3 adiciona sequenciamento dependente da sequência ao scheduler finito da 0.6.2. O motor passa a conhecer famílias de produto, matriz de troca, campanhas e regras de despacho EDD, SPT, Critical Ratio, prioridade comercial e minimização de setup.

## Destaques

- `ProductFamily` e `ItemSchedulingProfile` para família, campanha e prioridade comercial.
- `SequenceSetupRule` para setup `família origem → família destino`, por centro ou máquina.
- Novos parâmetros do cenário: `dispatch_rule`, `minimize_setups` e `campaign_mode`.
- Setup de sequência passa a consumir capacidade real do calendário industrial.
- Escolha de máquina/recurso inclui penalidade de setup na função de avaliação.
- Novos campos por bloco: `sequence_setup_hours`, `sequence_position` e `dispatch_score`.
- Resumo do cenário informa horas totais de setup dependente da sequência.
- API DRF para famílias, perfis de item e matriz de setup.
- Comando `simulate_sequence_schedule`.
- Tela de cenário mostra família, posição e setup por operação.

## Regras de despacho

- `EDD`: menor data de entrega primeiro.
- `SPT`: menor tempo de processamento primeiro.
- `CR`: menor Critical Ratio primeiro.
- `PRIORITY`: maior prioridade comercial primeiro.
- `SETUP_MIN`: agrupa família/campanha para reduzir trocas.

## Migração

`apps/integrated_scheduling/migrations/0004_advanced_sequence_063.py`

## Validação no ambiente de geração

A árvore Python foi compilada e validada por AST. O `manage.py check` e os testes Django devem ser executados dentro do Docker do projeto, pois o ambiente de geração não possui Django instalado diretamente.
