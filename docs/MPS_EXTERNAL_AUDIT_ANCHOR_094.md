# MPS 0.9.4 — Âncora externa de integridade

A 0.9.4 complementa a cadeia SHA-256 da 0.9.3 com uma cópia externa do `HEAD hash` em um ponto conhecido da trilha.

## Modelo de segurança

A cadeia no PostgreSQL continua tamper-evident. A âncora registra externamente `cockpit_id`, `anchored_sequence`, `anchored_head_hash`, instante e provider. A publicação grava o recibo com criação exclusiva (`O_EXCL`) e só depois adiciona o evento `ANCHOR_PUBLISHED` à cadeia. Dessa forma a âncora sempre referencia um ponto anterior e verificável da cadeia, evitando circularidade.

O backend padrão é `FILE_APPEND_ONLY`. Em produção, `MPS_AUDIT_ANCHOR_DIR` deve ser montado em armazenamento independente e preferencialmente WORM/imutável. Um diretório local comum não oferece proteção contra um administrador do host.

`MANUAL_EXTERNAL` permite registrar uma referência a um mecanismo externo não integrado, mas a aplicação não afirma que esse mecanismo foi verificado automaticamente.

## Verificação

A verificação confirma:

- integridade da cadeia atual;
- existência do evento na sequência ancorada;
- igualdade entre o hash daquele evento e `anchored_head_hash`;
- integridade do recibo salvo no banco;
- no provider `FILE_APPEND_ONLY`, integridade do recibo externo.

O HEAD atual pode ser diferente do HEAD ancorado, porque eventos posteriores são esperados.

## Operação

```bash
python manage.py anchor_mps_decision_audit --cockpit 42
python manage.py anchor_mps_decision_audit --cockpit 42 --verify
```

Produção:

```env
MPS_AUDIT_ANCHOR_DIR=/mnt/worm/mrp_audit_anchors
```

## Limitações

A aplicação não transforma um filesystem comum em WORM. A garantia mais forte depende da política do storage externo (Object Lock, retenção, WORM ou sistema independente). A âncora não é blockchain nem assinatura digital ICP-Brasil.
