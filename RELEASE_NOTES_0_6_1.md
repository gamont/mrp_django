# MRP 0.6.1 — Release notes

## Destaques

- programação finita por máquina;
- forward e backward scheduling;
- escolha de máquinas paralelas;
- uso opcional de `alternate_work_center` do roteiro;
- Gantt HTML interativo com drag-and-drop horizontal;
- bloqueio manual de blocos movidos;
- comparação/ranking de múltiplos cenários;
- publicação persistente do recurso por `PublishedOperationSchedule`;
- ações REST para simular, mover bloco, comparar e publicar;
- comando `simulate_finite_schedule`;
- migração `integrated_scheduling/0002_finite_gantt_scenarios.py`;
- testes de máquinas paralelas, movimento manual e comparação.

## Compatibilidade

Atualização incremental sobre 0.6.0. Execute `python manage.py migrate` antes de usar os novos campos e o modelo de publicação.

## Validação de geração

A árvore Python foi compilada e analisada por AST. `manage.py check`/pytest dependem do ambiente Django do projeto e devem ser executados no container Docker.
