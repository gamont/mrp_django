# Programação integrada 0.6.4 — otimizador multicritério

A 0.6.4 adiciona uma camada de exploração de soluções sobre o scheduler heurístico 0.6.3. Em vez de o planejador escolher uma única regra de despacho, o sistema gera vários cenários candidatos, executa o scheduler finito e compara os resultados por objetivos configuráveis.

## Objetivos

O score usa métricas normalizadas: atraso total, setup total, hora extra, atraso ponderado por prioridade comercial, desequilíbrio de utilização entre recursos e conflitos. Os pesos são normalizados para somar 1. Conflitos críticos tornam a solução não factível e recebem penalidade adicional.

## Estratégias candidatas

O conjunto inicial combina EDD, SPT, Critical Ratio, prioridade comercial e minimização de setup; inclui forward/backward e variantes com campanhas. Cada candidato é um `IntegratedScheduleScenario` completo, portanto pode ser aberto, inspecionado, ajustado manualmente e publicado com os mecanismos existentes.

## Pareto

Além do score ponderado, o sistema marca soluções não dominadas. Isso é útil quando duas soluções representam trade-offs: uma pode ter menos atraso, enquanto outra usa menos hora extra e setup.

## Limite matemático

A 0.6.4 é um otimizador de cenários heurísticos, não um solver MILP/CP-SAT global. Ele melhora a tomada de decisão e a comparação automática, mas não garante o ótimo global de um job-shop de grande porte.
