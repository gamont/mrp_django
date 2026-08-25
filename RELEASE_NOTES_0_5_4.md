# Release 0.5.4

## Terminal de chão de fábrica

- novo app `apps.shopfloor`;
- cadastro de máquinas e estações;
- perfil de operador com crachá e PIN hash;
- fila/dispatch por centro de trabalho;
- início de setup, execução, interrupção e conclusão;
- apontamento touch de produção;
- status da máquina em tempo real via polling HTMX;
- eventos de parada com motivo, início e fim;
- trilha por `DomainEvent`;
- migração `shopfloor/0001_initial`;
- comandos `seed_shopfloor` e `set_operator_pin`.
