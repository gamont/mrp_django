# Otimizador MPS 0.8.8

## Objetivo

Gerar alternativas de MPS e sourcing e avaliá-las pelo mesmo pipeline de what-if já usado pelo planejador.

## Estratégias

1. `BASELINE`: revisão atual, usada como referência operacional.
2. `SHIFT_LATER`: move uma fração de buckets não congelados para a semana seguinte.
3. `SHIFT_EARLIER`: move uma fração para a semana anterior quando elegível.
4. `LEVEL_LOAD`: aproxima buckets altos e baixos do mesmo item.
5. `SUPPLIER_TERMS`: sugere ItemSupplier alternativo quando o prazo de pagamento é maior e o preço fica dentro da tolerância configurada.

Mudanças em buckets `FROZEN` não são geradas automaticamente.

## Avaliação

Cada candidato dispara uma `MPSRevisionSimulation` e reaproveita:

- MRP: MAKE, PURCHASE, mensagens e pegging;
- RCCP comparativo;
- custo e estoque projetado;
- cash-flow temporal;
- working capital / CCC;
- financiamento e juros.

O ranking minimiza um score ponderado. Os pesos pertencem a `MPSOptimizationPolicy` e devem ser calibrados pela empresa.

## Aplicação

Candidatos de bucket só entram no plano quando um usuário escolhe **Adotar como revisão**. Isso atualiza os buckets do MPS operacional, recalcula RCCP e cria uma nova revisão DRAFT sujeita ao workflow normal de aprovação.

Candidatos `SUPPLIER_TERMS` nunca alteram sourcing mestre automaticamente. Eles são recomendações para Compras.

## API

- `POST /api/mps-revision-optimization-runs/run/`
- `GET /api/mps-revision-optimization-runs/{id}/report/`
- `POST /api/mps-revision-optimization-candidates/{id}/adopt/`
- recursos read-only de candidates/actions e CRUD da política.

## CLI

```bash
python manage.py optimize_mps_revision --revision 4 --compare 1
```

## Limites

A 0.8.8 é heurística, não um solver matemático global. O score não representa função contábil ou financeira oficial. Resultados dependem da qualidade de BOM, roteiros, custos, fornecedores, calendários, pedidos e políticas cadastradas.
