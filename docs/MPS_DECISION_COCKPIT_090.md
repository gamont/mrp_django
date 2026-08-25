# MPS Decision Cockpit 0.9.0

A versão 0.9.0 transforma a saída do otimizador Pareto em um processo executivo governado. O cockpit não cria um novo motor de planejamento: ele organiza e congela uma decisão baseada nas simulações já calculadas por MRP, RCCP, custo, cash-flow, capital de giro e financiamento.

## Fluxo

1. Uma `MPSRevisionOptimizationRun` CP-SAT Pareto precisa estar `COMPLETED`.
2. `MPSDecisionCockpit` importa todos os candidatos e cria `MPSDecisionCandidateReview`.
3. O usuário pode shortlistar, rotular e anotar cenários.
4. O gráfico permite escolher qualquer par de métricas da fronteira e comparar candidatos lado a lado.
5. Um candidato com `MPSRevisionSimulation` concluída é selecionado, com justificativa obrigatória na interface.
6. A decisão é submetida e deve ser aprovada por usuário diferente daquele que fez a seleção.
7. O cenário aprovado pode ser congelado como uma nova revisão `APPROVED` do MPS.
8. Congelar **não** publica `MasterProductionSchedule` e **não** executa MRP. A publicação operacional continua sendo uma etapa separada e respeita RCCP e demais controles.

## Segurança de governança

- O cockpit só nasce de uma otimização concluída.
- A seleção exige simulação concluída.
- Quem selecionou não aprova a própria decisão.
- Recomendações puramente de sourcing sem `candidate_mps_lines` não podem ser congeladas diretamente como MPS.
- O `decision_snapshot` preserva evidência da seleção, aprovação e congelamento.
- O congelamento materializa os buckets via mecanismo de adoção existente, recalcula RCCP e cria uma nova revisão oficial, sem apagar revisões anteriores.

## Interface

- `/integrated-schedule/decision-cockpit/`
- `/integrated-schedule/decision-cockpit/<id>/`

O gráfico é SVG/JavaScript puro, sem dependência externa. Os eixos podem alternar entre risco de serviço prospectivo, overload RCCP, financiamento descoberto, juros, exposição de estoque e compras.

## API

- `POST /api/mps-decision-cockpits/create-from-run/`
- `POST /api/mps-decision-cockpits/{id}/select/`
- `POST /api/mps-decision-cockpits/{id}/submit/`
- `POST /api/mps-decision-cockpits/{id}/approve/`
- `POST /api/mps-decision-cockpits/{id}/reject/`
- `POST /api/mps-decision-cockpits/{id}/freeze-official/`
- `GET /api/mps-decision-cockpits/{id}/compare/?left=<candidate>&right=<candidate>`

## CLI

```bash
python manage.py create_mps_decision_cockpit --run 31
```

## Limites deliberados

O cockpit é suporte à decisão, não um ERP financeiro/fiscal nem um substituto da aprovação humana. O campo `service_risk_proxy` continua sendo prospectivo e não deve ser interpretado como OTIF realizado. O cenário congelado ainda precisa passar pelo comando/ação de publicação do MPS para alimentar o `MasterProductionSchedule` oficial e, posteriormente, o MRP de produção.
