# MRP 0.9.6 — Security & Compliance Center

A versão 0.9.6 adiciona uma camada operacional de compliance sobre a cadeia auditável (0.9.3), âncoras externas (0.9.4) e política automática de proteção (0.9.5).

## Objetivos

- aplicar SLA de proteção diferente conforme a criticidade da decisão;
- detectar `STALE`, `UNPROTECTED`, `MISMATCH`, violações de SLA e evidências periódicas vencidas;
- abrir e resolver incidentes de compliance;
- alertar responsáveis por e-mail;
- gerar snapshots diários para indicadores executivos;
- exportar evidências periodicamente e reancorar o novo HEAD da cadeia.

## Criticidade

A criticidade é derivada da alçada atual da decisão:

- `EXECUTIVE_COMMITTEE` → `CRITICAL`;
- `DIRECTOR` → `HIGH`;
- demais casos → `STANDARD`.

Os SLAs padrão são 4h, 12h e 24h, respectivamente, e podem ser configurados por planta.

## Incidentes

Categorias: `STALE`, `UNPROTECTED`, `MISMATCH`, `SLA_BREACH` e `EVIDENCE_STALE`.
Estados: `OPEN`, `ACKNOWLEDGED`, `RESOLVED`.

O scanner resolve automaticamente um incidente quando a condição que o originou deixa de existir.

## Evidência periódica

Quando `auto_export_evidence=True`, um cockpit congelado e protegido recebe novo pacote de evidências se o último estiver mais antigo que `evidence_max_age_hours`. Como o próprio export adiciona um evento `EVIDENCE_EXPORTED`, a cadeia é ancorada novamente depois da exportação.

## Alertas

`alert_recipients` contém os destinatários. Em desenvolvimento, o backend de e-mail padrão continua sendo o console. Em produção, configure um backend SMTP/API apropriado.

## Indicadores

`MPSDecisionComplianceSnapshot` mantém por planta/dia:

- % de planos protegidos;
- % com pacote de evidências atual;
- tempo médio até a primeira âncora;
- divergências de integridade;
- incidentes em aberto.

## Automação

O Celery Beat executa `integrated_scheduling.run_mps_security_compliance` a cada hora. O job diário de âncoras da 0.9.5 permanece independente.

## Limites

O módulo é um centro de monitoramento e evidência da aplicação. Ele não substitui SIEM corporativo, HSM, PKI/ICP-Brasil, storage WORM real ou processos regulatórios específicos.

## Correção de compatibilidade da 0.9.5

A 0.9.5 introduziu dois providers obrigatórios, mas a restrição original da âncora ainda tornava único somente `cockpit + sequência + head_hash`. A migração 0.9.6 corrige a chave para incluir `provider`, permitindo que o mesmo ponto da cadeia seja ancorado legitimamente em storages primário e secundário.
