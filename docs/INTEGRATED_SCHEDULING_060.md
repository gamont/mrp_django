# Programação integrada 0.6.0

A versão 0.6.0 cria uma camada de simulação entre produção e manutenção. O princípio é preservar o cronograma real enquanto um cenário está em análise.

## Fluxo
1. O cenário captura operações de OP e OMs programadas dentro do horizonte.
2. O tempo de manutenção reduz a capacidade nominal do centro de trabalho.
3. Sobreposições são registradas como conflitos.
4. A simulação desloca conservadoramente operações que colidem com manutenção e preserva a sequência do centro.
5. A carga diária é comparada à capacidade remanescente.
6. O sistema registra risco de atraso e o impacto agregado.
7. Somente a ação Aplicar grava as novas datas em `WorkOrderOperation`.

## Segurança
Cenários concluídos com conflitos críticos não podem ser aplicados, salvo quando `parameters.allow_critical_conflicts=true` for definido explicitamente.

## Interface
`/integrated-schedule/`

## API
- `integrated-schedule-scenarios`
- `integrated-schedule-blocks`
- `integrated-schedule-conflicts`

Ações de cenário: `simulate` e `apply`.
