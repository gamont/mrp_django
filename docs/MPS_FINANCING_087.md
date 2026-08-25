# MPS 0.8.7 — capacidade financeira e linhas de crédito

A 0.8.7 adiciona uma camada de financiamento à simulação MPS. A necessidade de capital de giro calculada na 0.8.6 é comparada com linhas de crédito ativas da planta.

## Conceitos
- `FinancingPolicy`: controla utilização máxima das linhas e se a inviabilidade financeira bloqueia a aprovação da revisão.
- `FinancingFacility`: linha de crédito com limite, taxa anual, prioridade e vigência.
- `MPSRevisionSimulationFinancingBucket`: necessidade, saldo financiado, crédito disponível, necessidade não coberta e juros estimados por bucket.

## Regra de capacidade
`limite_utilizável = soma(limites ativos) × max_financing_utilization_percent`.

A necessidade por bucket usa o `working_capital_need` da 0.8.6. O saldo financiado é limitado ao crédito utilizável. O excedente fica em `uncovered_need`.

## Juros
Os juros são estimados de forma gerencial pela taxa anual ponderada pelos limites das facilities e pela duração do bucket. Não incluem IOF, tarifas, covenants, calendário bancário ou regras contratuais específicas.

## Governança
Se `block_revision_approval_when_exceeded=True`, uma revisão não-baseline só pode ser aprovada quando a simulação concluída possuir `financially_feasible.right=True`.
