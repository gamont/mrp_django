# MPS Compliance SLA & Escalation Engine — 0.9.7

A versão 0.9.7 adiciona escalonamento temporal aos incidentes criados pelo Security & Compliance Center 0.9.6.

## Fluxo

1. O scanner 0.9.6 cria ou atualiza `MPSDecisionComplianceIncident`.
2. O job 0.9.7 avalia incidentes `OPEN` e `ACKNOWLEDGED` a cada 15 minutos.
3. Regras são ativadas conforme minutos desde `first_seen_at`, severidade e categoria.
4. Cada regra cria no máximo um `MPSComplianceEscalationEvent` por incidente.
5. E-mails podem ser repetidos dentro de intervalo e limite configurados.
6. Quando o incidente é `RESOLVED`, os escalonamentos ativos são encerrados.

## Níveis

`TEAM → MANAGER → DIRECTOR → EXECUTIVE`.

A instalação não presume que todo incidente precise atingir todos os níveis. As regras podem filtrar severidades e categorias.

## Plantão

`MPSComplianceOnCallContact` aceita dias da semana, janela de horário e níveis atendidos. Um contato com listas/janelas vazias é considerado disponível sem restrição adicional. Para produção, o fuso horário é o `TIME_ZONE` do Django.

## Repetição controlada

A política define `repeat_interval_minutes` e `max_repeat_notifications`. A regra pode sobrescrever ambos. `notification_count` é persistido no evento e impede tempestade ilimitada de e-mails.

## MTTA e MTTR

- MTTA: `acknowledged_at - first_seen_at`.
- MTTR: `resolved_at - first_seen_at`.

São métricas operacionais do workflow de compliance e não substituem indicadores de incident management corporativo quando houver uma ferramenta oficial externa.

## Celery

`integrated_scheduling.run_mps_compliance_escalation` roda por padrão a cada 900 segundos.

## Seed

```bash
python manage.py seed_mps_compliance_escalation --plant SP01 --email compliance@example.com
```

Os tempos do seed são exemplos: equipe imediatamente para HIGH/CRITICAL; gerente em 30 min; diretor em 60 min para CRITICAL; executivo em 120 min para CRITICAL. Ajuste à política real antes de produção.
