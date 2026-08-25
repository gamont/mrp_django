# Release 0.7.7

## Gestão gerencial de nível de serviço

- `ServiceLevelTarget` para metas por planta, cliente, família e item.
- `ServiceLevelPeriodSnapshot` para histórico mensal.
- OTIF, On-Time, In-Full, fill rate, backlog vencido e custo estimado da falha de serviço.
- `perfect_order_proxy_pct`, explicitamente identificado como proxy por falta de dados documentais/avaria.
- ranking analítico por cliente/família/item/planta.
- Pareto de causas por snapshot.
- dashboard gerencial e tendência mensal.
- endpoints DRF para metas e snapshots.
- comandos `seed_service_level_targets` e `build_service_level_snapshots`.
- migração `0018_service_level_management_077.py`.
