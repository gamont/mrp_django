# 0.7.1 — Event-driven recovery scheduling

A versão 0.7.1 liga eventos reais da fábrica ao recovery scheduling. `DowntimeEvent` não planejado e `LaborUnavailability` que afetam o cronograma oficial geram `ReschedulingTrigger`. Faltas de material são detectadas pelo scan do cronograma oficial contra reservas de OP.

O recovery preserva o frozen horizon: operações congeladas são removidas das decisões do solver e reaparecem no cenário como perdas fixas de capacidade. O CP-SAT otimiza somente a parte recuperável. O planejador compara plano atual × recuperado e publica explicitamente uma nova versão; o cronograma oficial nunca é substituído silenciosamente.
