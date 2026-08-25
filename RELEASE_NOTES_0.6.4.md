# Release 0.6.4 — Otimizador multicritério

A 0.6.4 adiciona exploração automática de soluções ao scheduler finito. Uma execução de otimização cria de 2 a 12 cenários candidatos com estratégias EDD, SPT, Critical Ratio, prioridade comercial, minimização de setup, campanhas e forward/backward.

## Novidades

- `ScheduleOptimizationRun` e `ScheduleOptimizationCandidate`.
- Pesos configuráveis para atraso, setup, overtime, atraso prioritário, desequilíbrio de utilização e conflitos.
- Normalização automática dos KPIs por execução.
- Penalidade de inviabilidade para conflitos críticos.
- Ranking por score multicritério: menor é melhor.
- Identificação de soluções não dominadas na fronteira de Pareto.
- Tela de ranking com acesso ao cenário completo de cada candidato.
- API `/api/schedule-optimization-runs/optimize/`.
- Comando `optimize_schedule`.
- Migração `0005_multicriteria_optimizer_064.py`.

## Observação

O otimizador continua heurístico: ele compara várias políticas e configurações do scheduler existente; não promete ótimo global matemático.
