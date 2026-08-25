# Release 0.5.5

## OEE e monitoramento do chão de fábrica

- cálculo diário de OEE por máquina;
- disponibilidade = tempo operacional / tempo planejado;
- performance baseada no ciclo ideal e quantidade total produzida;
- qualidade baseada em quantidade boa / quantidade total;
- MTBF e MTTR com base em paradas não planejadas;
- vínculo do apontamento de produção com a máquina que executou a operação;
- snapshots diários persistidos para histórico;
- painel Andon em `/shopfloor/andon/`, com atualização HTMX a cada 15 segundos;
- OEE resumido também no terminal da máquina;
- comando `calculate_oee --plant <PLANTA> [--date YYYY-MM-DD]`;
- parâmetros de máquina `planned_minutes_per_day` e `ideal_cycle_seconds`;
- migração `shopfloor/0002_oee_monitoring`;
- testes básicos de OEE, qualidade e confiabilidade.

### Fórmulas

- Disponibilidade = (tempo planejado - parada) / tempo planejado
- Performance = (ciclo ideal × quantidade total) / tempo operacional
- Qualidade = quantidade boa / (quantidade boa + refugo)
- OEE = disponibilidade × performance × qualidade
- MTBF = tempo operacional / número de falhas não planejadas
- MTTR = tempo de parada não planejada / número de falhas

A performance é limitada a 100% para proteger o indicador contra cadastros inconsistentes de ciclo ideal.
