# MRP 0.6.8 — Mão de obra finita no CP-SAT

A versão 0.6.8 acrescenta uma terceira dimensão de capacidade ao scheduler: **máquina + mão de obra + calendário**.

## Modelo

- `LaborSkill`: competência industrial.
- `LaborResource`: operador ou técnico disponível para programação.
- `LaborResourceSkill`: proficiência 1–5 e validade.
- `LaborShiftAssignment`: vínculo do recurso humano a um `WorkCenterShift`.
- `LaborUnavailability`: férias, treinamento, afastamento ou indisponibilidade pontual.
- `OperationLaborRequirement`: skill, proficiência e quantidade mínima de pessoas por operação.
- `ScheduleSolverLaborAssignment`: equipe realmente escolhida pelo CP-SAT.

`LaborResource` pode apontar para `shopfloor.OperatorProfile` ou `maintenance.TechnicianProfile`, permitindo reutilizar cadastros já existentes.

## Restrições do solver

Quando `use_labor_constraints=true`, uma alternativa de máquina/janela só pode ser escolhida se houver, simultaneamente, a quantidade necessária de pessoas qualificadas no mesmo intervalo. Cada pessoa recebe um `NoOverlap`, portanto não pode ser alocada em duas operações ao mesmo tempo.

A disponibilidade humana é gerada a partir dos turnos do centro, descontando `IndustrialShiftBreak` e `LaborUnavailability`. `min_rest_hours` adiciona um buffer entre alocações consecutivas do mesmo recurso.

No modo preemptivo, a equipe é escolhida por segmento. Isso permite troca de equipe entre turnos. Para requisitos com `allow_shift_handoff=false`, o modelo força a mesma composição de trabalhadores em todos os segmentos.

## Preparação

Sincronize os perfis já existentes:

```bash
python manage.py sync_finite_labor --plant SP01
```

Depois cadastre skills, proficiências, turnos e requisitos por operação pelo Admin ou API.

## Execução

```bash
python manage.py solve_cp_sat_schedule \
  --scenario 15 \
  --preemptive \
  --max-consecutive-minutes 240 \
  --time-limit 300
```

Para comparar com o solver sem mão de obra:

```bash
python manage.py solve_cp_sat_schedule --scenario 15 --no-labor
```

## Limites desta versão

A capacidade humana é individual e finita, mas ainda não há otimização explícita de custo de mão de obra, preferência de operador, overtime individual ou legislação trabalhista completa. `min_rest_hours` é uma regra técnica simplificada de descanso entre alocações. Esses itens ficam preparados para evolução posterior.
