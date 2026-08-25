# Release 0.9.3 — Audit trail encadeada e pacote de evidências

- `MPSDecisionAuditEvent`: eventos numerados, `previous_hash` e `event_hash` SHA-256.
- `verify_audit_chain()`: valida sequência e integridade.
- Hooks em criação/seleção/submissão/alçada/assinatura/aprovação/rejeição/congelamento/exportação.
- `MPSDecisionEvidenceExport`: manifesto e SHA-256 do pacote exportado.
- ZIP de evidências com cadeia, assinaturas, snapshot e anexos locais quando disponíveis.
- UI `/decision-cockpit/<id>/audit/`, API read-only/verify/export e comando `export_mps_decision_evidence`.
- Admin da cadeia sem add/change/delete normais.

Limite: a cadeia é tamper-evident, não WORM externo. Um DBA com controle total pode reescrever dados e hashes; preserve o hash/pacote fora do banco para uma âncora independente.
