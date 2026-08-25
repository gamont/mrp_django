# Programação CP-SAT segmentável — 0.6.7

## Objetivo

O modo preemptivo resolve uma limitação do CP-SAT 0.6.5/0.6.6: uma operação não precisa mais caber inteira em uma única janela contínua do calendário. Ela pode ser dividida em trechos sequenciais, preservando a mesma máquina e a precedência tecnológica.

## Exemplo

Uma operação exige 6 horas. Há capacidade das 10:00–12:00 e 13:00–17:00. Com `preemptive_operations=true`, o modelo pode criar dois segmentos de 2 h e 4 h. O período 12:00–13:00 não consome máquina nem tempo produtivo.

## Limite consecutivo

`max_consecutive_minutes` define o maior trecho contínuo de uma operação. Uma operação de 10 h com limite de 240 min é decomposta em 4 h + 4 h + 2 h antes da construção das alternativas CP-SAT.

## Handoff

Quando um segmento não começa imediatamente após o anterior, há um handoff. A variável correspondente pode receber penalidade pelo parâmetro `handoff_penalty`, permitindo ao solver preferir menos interrupções quando as demais métricas forem equivalentes.

## Restrições preservadas

- `NoOverlap` por máquina/centro;
- bloqueios de manutenção;
- janelas regulares e de overtime;
- precedência entre operações de uma OP;
- máquina/centro alternativo;
- setup dependente da sequência;
- datas de entrega e prioridade comercial;
- warm start, gap, Celery e cancelamento da 0.6.6.

## Persistência

`ScheduleSolverAssignment` continua representando o envelope da operação. `ScheduleSolverSegment` guarda cada trecho. Ao aplicar ao cenário, os mesmos trechos são convertidos em `IntegratedScheduleSegment` para uso no Gantt e relatórios.

## Próxima evolução possível

A formulação atual mantém todos os segmentos na mesma máquina. Uma evolução posterior pode modelar handoff entre operadores, skills por turno, transferência controlada entre recursos equivalentes e limites de WIP entre segmentos.
