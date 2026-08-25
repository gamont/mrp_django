# Release 0.9.0 — Executive MRP/MPS Decision Cockpit

## Destaques

- Cockpit executivo sobre uma otimização CP-SAT Pareto concluída.
- Gráfico SVG interativo com troca de eixos para critérios MRP/RCCP/financeiros.
- Comparação lado a lado de dois candidatos.
- Shortlist, rótulos de negócio e notas executivas por cenário.
- Seleção com justificativa e workflow `OPEN → SELECTED → PENDING_APPROVAL → APPROVED → FROZEN`.
- Regra de segregação: quem seleciona não pode aprovar a própria decisão.
- Congelamento do cenário como nova revisão oficial `APPROVED`, sem publicar MPS ou executar MRP automaticamente.
- Snapshot auditável da decisão.
- API DRF, UI e comando `create_mps_decision_cockpit`.
- Migração `0031_mps_decision_cockpit_090.py`.

## Upgrade

```bash
docker compose build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py check
docker compose run --rm web pytest
docker compose up -d
```

Depois de uma otimização Pareto concluída:

```bash
python manage.py create_mps_decision_cockpit --run 31
```
