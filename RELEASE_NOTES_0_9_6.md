# Release 0.9.6 — Security & Compliance Center

- política de compliance por planta;
- SLA por criticidade `STANDARD/HIGH/CRITICAL`;
- incidentes `STALE`, `UNPROTECTED`, `MISMATCH`, `SLA_BREACH`, `EVIDENCE_STALE`;
- reconhecimento e resolução automática de incidentes;
- alertas por e-mail;
- exportação periódica de evidências com reancoragem;
- snapshots de KPIs de compliance;
- painel `/integrated-schedule/security-compliance/`;
- API, comandos, Admin e Celery Beat horário;
- versão interna atualizada para 0.9.6.
- correção da unicidade de âncoras: o provider agora faz parte da chave lógica, permitindo ancoragem primária e secundária do mesmo HEAD, como previsto na 0.9.5.
