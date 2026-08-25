# 0.8.1 — MPS operacional interativo

A 0.8.1 permite editar buckets semanais antes da publicação, mover volume entre semanas do mesmo item, recalcular RCCP após cada alteração e preservar o delta em relação ao baseline gerado a partir do S&OP.

## Governança de time fence

Buckets FROZEN não são alterados diretamente. A mudança gera `MPSBucketChangeRequest` em estado `PENDING` e precisa ser aprovada por um segundo usuário. Aprovação aplica a mudança e recalcula RCCP; rejeição preserva o plano atual.

Buckets FIRM e PLANNED podem ser ajustados diretamente, mas toda alteração fica registrada como change request aprovado automaticamente.

## Ações

- editar quantidade de um bucket;
- mover volume entre semanas do mesmo item;
- consultar baseline e delta;
- aprovar/rejeitar violação de frozen horizon;
- recalcular RCCP automaticamente.

## API

- `POST /api/mps-weekly-buckets/{id}/edit_quantity/`
- `POST /api/mps-weekly-buckets/{id}/move_volume/`
- `GET /api/mps-bucket-change-requests/`
- `POST /api/mps-bucket-change-requests/{id}/approve/`
- `POST /api/mps-bucket-change-requests/{id}/reject/`
