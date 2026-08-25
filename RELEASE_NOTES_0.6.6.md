# Release Notes — MRP Django 0.6.6

## Solver CP-SAT operacional

A 0.6.6 evolui o solver CP-SAT introduzido na 0.6.5 com recursos de execução industrial: warm start a partir do melhor cenário heurístico, gap relativo configurável, execução assíncrona com Celery/Redis, cancelamento cooperativo, histórico de incumbents e comparação CP-SAT × heurístico × cronograma publicado.

### Banco de dados

Nova migração `apps/integrated_scheduling/migrations/0007_solver_async_warmstart_066.py`.

`ScheduleSolverRun` recebe modo de execução, gap, origem do warm start, task Celery, timestamps, cancelamento e progresso. O novo `ScheduleSolverIncumbent` preserva a evolução da busca.

### Infraestrutura

`requirements.txt` agora inclui Celery e Redis. `docker-compose.yml` adiciona `redis` e `worker`. O worker aguarda o web ficar saudável e pula o bootstrap Django duplicado.

### API/UI

A execução pode ser assíncrona, há ação de cancelamento, histórico de incumbents e tela de comparação de métodos.

### Compatibilidade

O caminho síncrono da 0.6.5 permanece disponível. OR-Tools continua opcional apenas fora da imagem atualizada; a imagem Docker instala a dependência declarada.

### Validação no ambiente de geração

- `compileall`: OK.
- parsing AST: OK.
- integridade do ZIP: deve ser validada no empacotamento.
- `manage.py check`/`pytest`: dependem do ambiente Docker com Django instalado.
