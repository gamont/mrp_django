# MPS Decision Audit 0.9.3

A versão 0.9.3 adiciona uma trilha append-only, encadeada por SHA-256, para os eventos críticos do cockpit MPS. Cada evento inclui o hash do evento anterior e um hash canônico de seu conteúdo. `verify_audit_chain()` detecta quebra de sequência, alteração do hash anterior ou alteração do payload.

O pacote ZIP de evidências inclui `manifest.json`, `audit_chain.json`, `electronic_signatures.json`, `decision_snapshot.json` e, quando o storage expõe arquivos locais, os anexos com SHA-256 individual. O SHA-256 do próprio ZIP é persistido em `MPSDecisionEvidenceExport`.

Isto fornece evidência de integridade dentro da aplicação; não é blockchain pública, carimbo do tempo ICP-Brasil nem WORM externo. Para resistência contra administrador de banco com acesso irrestrito, exporte e preserve o pacote/hash em storage externo imutável.
