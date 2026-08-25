# MRP Django 0.6.0

Marco de programação integrada Produção + Manutenção.

## Novidades
- Novo app `integrated_scheduling`.
- Cenários what-if persistidos, sem alteração dos dados reais até aplicar.
- Visão única de operações produtivas e ordens de manutenção por centro de trabalho.
- Capacidade diária reduzida por janelas de manutenção.
- Detecção de sobreposição manutenção × produção.
- Detecção de sobrecarga após perda de capacidade.
- Projeção conservadora de deslocamento das operações e risco de atraso.
- Resumo de impacto para decisão CTP/capacidade.
- Aplicação explícita do cenário às datas planejadas das operações.
- API DRF, UI e comando `simulate_integrated_schedule`.

## Observação de escopo
O indicador de impacto CTP desta versão é derivado da capacidade e dos atrasos projetados das OPs. Ele não substitui o motor material/ATP/CTP existente; serve para mostrar o efeito da indisponibilidade de recursos antes de confirmar a parada. Uma evolução posterior pode reexecutar automaticamente o CTP material completo a partir do cenário.
