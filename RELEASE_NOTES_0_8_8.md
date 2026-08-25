# MRP Django 0.8.8 — Otimização multicritério do MPS

A versão 0.8.8 adiciona um otimizador heurístico de alternativas para revisões do MPS operacional. O objetivo é comparar cenários antes da aprovação usando os motores já existentes de MRP what-if, RCCP, custo, cash-flow, capital de giro e financiamento.

## Principais entregas

- `MPSOptimizationPolicy`: pesos, número máximo de candidatos, percentual de volume movido, tolerância de preço e opção de fornecedor alternativo.
- `MPSRevisionOptimizationRun`, `Candidate` e `Action`: execução auditável, ranking e explicação das ações sugeridas.
- Estratégias iniciais: revisão atual, postergar volume, antecipar volume, nivelar buckets e fornecedor alternativo com prazo financeiro melhor.
- Cenários de bucket são mantidos em `planning_overrides`; não criam revisões fantasma nem alteram o MPS oficial durante a simulação.
- `MPSRevisionSimulation.planning_overrides` permite executar o MRP com um MPS inline alternativo e/ou sourcing alternativo.
- Fornecedor alternativo afeta valoração, cash-flow e AP/working capital do lado target, sem mudar o cadastro mestre automaticamente.
- Score menor é melhor e combina faltas, overload RCCP, necessidade financeira não coberta, juros, estoque e compras. Cenário financeiramente inviável recebe forte penalidade.
- Candidato de buckets pode ser adotado como nova revisão formal; fornecedor alternativo permanece recomendação de sourcing para decisão de Compras.
- API, Celery, management command e tela de ranking.
- Política opcional `require_optimizer_before_approval` para exigir uma execução concluída antes da aprovação da revisão.

## Segurança operacional

O otimizador não publica MPS, não executa criação de OC/OP, não altera fornecedor primário e não aprova revisões automaticamente. A recomendação é apoio à decisão humana.
