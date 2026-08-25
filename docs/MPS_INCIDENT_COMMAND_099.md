# MPS Incident Command & Postmortem — 0.9.9

A versão 0.9.9 transforma incidentes críticos de compliance em um processo formal de resposta e aprendizado. Um incidente pode ser promovido manualmente ou automaticamente quando a política da planta combina severidade CRITICAL com escalonamento EXECUTIVE.

## Fluxo

1. compliance incident / escalation;
2. major incident e nomeação de commander;
3. war room e timeline operacional;
4. contenção, ações corretivas e preventivas;
5. resolução;
6. postmortem com causa raiz, 5 Whys e fatores contribuintes;
7. learning actions que apontam para MRP, MPS, compliance, escalation, master data ou processo;
8. fechamento formal.

SEV1/SEV2 exigem postmortem aprovado antes do fechamento pela política padrão. Ações ainda OPEN/IN_PROGRESS também bloqueiam o fechamento.

## Limites

O módulo é um workflow operacional de incident command. Ele não substitui ITSM, gestão corporativa de continuidade, investigação legal, ou ferramentas especializadas de segurança. O campo `war_room_url` apenas referencia a sala externa; a 0.9.9 não cria videoconferência.
