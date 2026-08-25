# MRP 0.8.2 — Versionamento e comparação de MPS

A 0.8.2 adiciona governança de revisão ao MPS operacional semanal. Cada estado relevante do MPS pode ser preservado como uma `MPSRevision`, contendo cópia dos buckets e do resultado RCCP daquele momento.

## Fluxo

1. O primeiro MPS construído cria `r1 / BASELINE / APPROVED`.
2. Alterações aplicadas nos buckets geram uma nova revisão `DRAFT`.
3. A revisão inteira é submetida para aprovação.
4. O autor não pode aprovar a própria revisão.
5. Uma publicação normal exige que a revisão mais recente esteja `APPROVED`.
6. Uma revisão anterior pode ser restaurada por rollback; o rollback cria uma nova revisão `DRAFT`, preservando o histórico.

## Diff

`compare_revisions()` compara item + semana e mostra quantidade anterior, nova, delta e mudança de status do bucket. Também calcula:

- alteração líquida e absoluta do MPS;
- número de itens/buckets afetados;
- alterações dentro de buckets congelados;
- diferença de horas de sobrecarga RCCP e número de exceções críticas.

O campo `estimated_mrp_impact` é deliberadamente uma **estimativa pré-MRP**. Ele mede o que mudou no MPS; não tenta adivinhar explosão de BOM, netting, ordens planejadas ou mensagens de exceção. Esses resultados só existem após executar o MRP real.

## Upgrade 0.8.1 → 0.8.2

Publicações criadas na 0.8.1 não possuem snapshot de revisão. Execute:

```bash
python manage.py backfill_mps_revisions
```

Isso cria uma revisão baseline aprovada a partir do estado atual de cada publicação ainda sem histórico.

## CLI

```bash
python manage.py mps_revision --publication 15 --capture --label "Plano antes da revisão comercial"
python manage.py mps_revision --publication 15 --compare 1 3
python manage.py mps_revision --publication 15 --rollback 1 --reason "Voltar ao baseline"
```

## API

- `GET /api/mps-revisions/`
- `POST /api/mps-revisions/capture/`
- `POST /api/mps-revisions/{id}/submit/`
- `POST /api/mps-revisions/{id}/approve/`
- `POST /api/mps-revisions/{id}/reject/`
- `GET /api/mps-revisions/{id}/compare/?other=<id>`
- `POST /api/mps-revisions/{id}/rollback/`
- `GET /api/mps-revision-lines/`
- `GET /api/mps-revision-rccp-lines/`
