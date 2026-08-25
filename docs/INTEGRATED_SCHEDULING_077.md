# 0.7.7 — Gestão gerencial de nível de serviço

A 0.7.7 consolida os resultados OTIF da 0.7.6 em indicadores gerenciais por planta, cliente, família de produto e item.

## Indicadores

- OTIF, On-Time e In-Full.
- Fill rate em quantidade: quantidade entregue / quantidade pedida.
- Backlog vencido em quantidade, usando a data de compromisso efetiva com o cliente.
- Meta por planta, cliente, família ou item, com vigência.
- Pareto de causas a partir de `ServiceLevelCause` / `primary_cause`.
- Tendência mensal através de snapshots persistidos.
- Custo estimado de falha de serviço, parametrizado por custo por dia de atraso e custo por unidade incompleta.

## Perfect Order

O sistema ainda não possui fatos suficientes para um Perfect Order completo (acurácia documental/faturamento, ausência de avaria e outros requisitos). Por isso a 0.7.7 expõe `perfect_order_proxy_pct`: linha OTIF entregue em uma única remessa. O campo e a UI identificam explicitamente que se trata de um proxy.

## Metas

`ServiceLevelTarget` suporta escopos `PLANT`, `CUSTOMER`, `FAMILY` e `ITEM`, com vigência e fallback para a meta da planta.

## Snapshots

`ServiceLevelPeriodSnapshot` preserva os KPIs mensais e permite tendências sem recalcular toda a história em cada acesso.

```bash
python manage.py seed_service_level_targets --plant SP01
python manage.py build_service_level_snapshots --plant SP01 --year 2026 --month 8
```

A tela gerencial está em `/integrated-schedule/service-level/management/`.
