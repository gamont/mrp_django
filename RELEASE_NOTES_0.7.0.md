# MRP 0.7.0

## Publicação e execução do plano ótimo

- versão oficial de cronograma por planta;
- publicação de solver CP-SAT `OPTIMAL`/`FEASIBLE`;
- horizonte congelado;
- slots oficiais por operação/máquina/equipe;
- compatibilidade com `PublishedOperationSchedule` legado;
- planned × actual;
- desvios de início e término;
- gatilhos idempotentes de replanejamento;
- cenário de replanejamento por quebra, falta de material, ausência e prioridade;
- API, Admin, UI e comandos de gerenciamento;
- migração `0011_execution_publication_070.py`.

A publicação continua sendo explícita: um evento prepara o replanejamento, mas não substitui o cronograma oficial sem aprovação/publicação.
