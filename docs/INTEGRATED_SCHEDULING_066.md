# Integrated Scheduling 0.6.6

## Objetivo

A versão 0.6.6 transforma o CP-SAT da 0.6.5 em um serviço de otimização operacional: warm start, gap configurável, execução assíncrona com Celery/Redis, cancelamento cooperativo, histórico de incumbents e comparação com o melhor heurístico e o cronograma publicado.

## Warm start

Quando `warm_start_enabled=true`, o solver procura a execução de otimização multicritério mais recente do cenário-base. Se houver um `best_candidate`, seus horários e recursos são usados como hints do CP-SAT. Na ausência dele, o cenário simulado atual é usado como ponto de partida.

Campos de auditoria: `warm_start_source` e `warm_start_scenario`.

## Gap relativo

`relative_gap_limit` é repassado para `CpSolver.parameters.relative_gap_limit`. Exemplos:

- `0`: não encerra por gap; o solver continua até provar ótimo ou atingir outro limite.
- `0.02`: permite encerramento quando o gap relativo chega a aproximadamente 2%.
- `0.05`: perfil mais rápido, com tolerância de 5%.

No CP-SAT, `OPTIMAL` também pode ser retornado quando um gap configurado é atingido. Por isso a aplicação distingue `global_optimum_proven` (somente `OPTIMAL` com gap configurado em zero) de `success_with_gap_tolerance`. `FEASIBLE` continua indicando solução válida sem encerramento de sucesso/ótimo.

## Execução assíncrona

A stack passa a incluir Redis e um worker Celery. O endpoint e a tela aceitam execução assíncrona. O web process cria `ScheduleSolverRun`, enfileira `integrated_scheduling.run_cp_sat` e retorna imediatamente.

Serviços do Docker Compose:

- `db`: PostgreSQL
- `redis`: broker/result backend
- `web`: Django/Gunicorn
- `worker`: Celery

## Cancelamento

O cancelamento é cooperativo. `cancel_requested_at` é persistido no banco. O callback do CP-SAT consulta esse campo sempre que um novo incumbent é encontrado e chama `StopSearch()`.

Isso evita encerramento forçado do processo do worker. Em problemas sem incumbents frequentes, o cancelamento pode não ser instantâneo.

## Incumbents

Cada nova solução incumbente registra `ScheduleSolverIncumbent` com:

- sequência;
- objetivo;
- best bound;
- gap relativo;
- wall time;
- resumo da solução.

A tela do solver atualiza automaticamente enquanto a execução estiver `DRAFT` ou `RUNNING`.

## Comparação de métodos

A rota `/integrated-schedule/<scenario>/solver-compare/` compara, quando disponíveis:

1. melhor candidato heurístico do otimizador 0.6.4;
2. execução CP-SAT mais recente com solução factível;
3. cronograma publicado para o cenário.

Métricas não equivalentes entre motores aparecem como `-` para evitar comparações falsas.

## API

- `POST /api/schedule-solver-runs/solve/` — síncrono ou assíncrono (`async=true`).
- `POST /api/schedule-solver-runs/{id}/cancel/` — solicita cancelamento.
- `GET /api/schedule-solver-runs/compare-methods/?scenario_id=<id>` — comparação.
- `GET /api/schedule-solver-incumbents/?run=<id>` — histórico de incumbents.

## CLI

```bash
python manage.py solve_cp_sat_schedule \
  --scenario 15 \
  --time-limit 600 \
  --workers 8 \
  --granularity 5 \
  --relative-gap 0.02 \
  --async
```

Cancelar:

```bash
python manage.py cancel_cp_sat_schedule --run 42 --reason "Replanejamento solicitado"
```

## Operação recomendada

Para cenários pequenos, execução síncrona ainda é útil. Para horizontes maiores ou limites acima de 30–60 segundos, use Celery para não ocupar um worker HTTP do Gunicorn.
