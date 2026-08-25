# MRP Django 0.5.7

## Manutenção industrial integrada

- Novo app `apps.maintenance`.
- Cadastro de ativos e criticidade.
- Leitura de horímetro/contador.
- Planos preventivos por calendário, medidor ou híbrido.
- Geração automática de ordens preventivas.
- Ordens preventiva, corretiva, preditiva e de inspeção.
- Integração de OM com `Machine`, `DowntimeEvent` e OEE.
- Corretivas classificadas como parada não planejada para MTBF/MTTR.
- Preventivas classificadas como parada planejada.
- Falhas com sintoma, causa, ação corretiva e resolução.
- Peças de reposição com baixa real em estoque e idempotência.
- Dashboard Django + HTMX em `/maintenance/`.
- API DRF de ativos, planos, ordens, peças, leituras e falhas.
- Novo papel `MRP Manutenção`.
- Comandos `seed_maintenance` e `generate_maintenance_orders`.
- Migração `apps/maintenance/migrations/0001_initial.py`.
- Testes de preventiva e consumo de peças.
