from __future__ import annotations
import hashlib, json, os
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import MPSDecisionAuditAnchor, MPSDecisionAuditEvent
from .mps_decision_audit import verify_audit_chain, append_audit_event, GENESIS


def _canonical(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _receipt_hash(receipt):
    return hashlib.sha256(_canonical(receipt).encode("utf-8")).hexdigest()


def _anchor_dir(provider=MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY):
    if provider == MPSDecisionAuditAnchor.Provider.FILE_SECONDARY:
        return Path(getattr(settings, "MPS_AUDIT_ANCHOR_SECONDARY_DIR", "/var/lib/mrp/audit_anchors_secondary"))
    return Path(getattr(settings, "MPS_AUDIT_ANCHOR_DIR", "/var/lib/mrp/audit_anchors"))


def _chain_hash_at(cockpit, sequence):
    if sequence == 0:
        return GENESIS
    event = cockpit.audit_events.filter(sequence=sequence).only("event_hash").first()
    return event.event_hash if event else None


@transaction.atomic
def publish_external_anchor(cockpit, actor=None, provider=MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY, external_reference=""):
    verification = verify_audit_chain(cockpit)
    if not verification["ok"]:
        raise ValueError("A cadeia de auditoria está inconsistente; a âncora não pode ser publicada.")
    seq = verification["event_count"]
    head = verification["head_hash"]
    receipt = {
        "schema": "MRP-MPS-AUDIT-ANCHOR-0.9.4",
        "cockpit_id": cockpit.id,
        "anchored_sequence": seq,
        "anchored_head_hash": head,
        "anchored_at": timezone.now().isoformat(),
        "provider": provider,
    }
    ref = external_reference
    if provider in {MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY, MPSDecisionAuditAnchor.Provider.FILE_SECONDARY}:
        root = _anchor_dir(provider); root.mkdir(parents=True, exist_ok=True)
        name = f"cockpit_{cockpit.id}_seq_{seq}_{head[:16]}.anchor.json"
        path = root / name
        raw = (_canonical(receipt) + "\n").encode("utf-8")
        # O_EXCL prevents accidental overwrite; mount this directory on WORM/immutable storage in production.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o440)
        try:
            os.write(fd, raw); os.fsync(fd)
        finally:
            os.close(fd)
        ref = str(path)
        receipt["external_reference"] = ref
    elif not ref:
        raise ValueError("external_reference é obrigatório para MANUAL_EXTERNAL.")
    rh = _receipt_hash(receipt)
    anchor = MPSDecisionAuditAnchor.objects.create(
        cockpit=cockpit, provider=provider, anchored_sequence=seq, anchored_head_hash=head,
        anchored_at=timezone.now(), external_reference=ref, receipt=receipt, receipt_hash=rh,
        status=MPSDecisionAuditAnchor.Status.ANCHORED,
        created_by=actor if actor and getattr(actor, "is_authenticated", False) else None,
    )
    append_audit_event(cockpit, MPSDecisionAuditEvent.EventType.ANCHOR_PUBLISHED, actor, {
        "anchor_id": anchor.id, "provider": provider, "anchored_sequence": seq,
        "anchored_head_hash": head, "receipt_hash": rh, "external_reference": ref,
    })
    return anchor


def verify_external_anchor(anchor, actor=None, append_event=False):
    cockpit = anchor.cockpit
    chain = verify_audit_chain(cockpit)
    errors = []
    actual_at_point = _chain_hash_at(cockpit, anchor.anchored_sequence)
    if actual_at_point is None:
        errors.append("anchored_sequence_missing")
    elif actual_at_point != anchor.anchored_head_hash:
        errors.append("anchored_head_hash_mismatch")
    if _receipt_hash(anchor.receipt or {}) != anchor.receipt_hash:
        errors.append("receipt_hash_mismatch")
    external_ok = None
    if anchor.provider in {MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY, MPSDecisionAuditAnchor.Provider.FILE_SECONDARY}:
        try:
            raw = Path(anchor.external_reference).read_text(encoding="utf-8").strip()
            external_receipt = json.loads(raw)
            external_ok = _receipt_hash(external_receipt) == anchor.receipt_hash
            if not external_ok:
                errors.append("external_receipt_mismatch")
        except Exception as exc:
            external_ok = False; errors.append(f"external_receipt_unavailable:{exc.__class__.__name__}")
    details = {
        "ok": not errors and chain["ok"], "chain_ok": chain["ok"], "anchor_errors": errors,
        "current_head_hash": chain["head_hash"], "current_event_count": chain["event_count"],
        "anchored_sequence": anchor.anchored_sequence, "anchored_head_hash": anchor.anchored_head_hash,
        "actual_hash_at_anchor_point": actual_at_point, "external_receipt_ok": external_ok,
    }
    anchor.status = MPSDecisionAuditAnchor.Status.VERIFIED if details["ok"] else MPSDecisionAuditAnchor.Status.MISMATCH
    anchor.verified_at = timezone.now(); anchor.verification_details = details
    anchor.save(update_fields=["status", "verified_at", "verification_details", "updated_at"])
    if append_event:
        append_audit_event(cockpit, MPSDecisionAuditEvent.EventType.ANCHOR_VERIFIED, actor, {
            "anchor_id": anchor.id, "ok": details["ok"], "anchored_sequence": anchor.anchored_sequence,
            "anchored_head_hash": anchor.anchored_head_hash,
        })
    return details


def verify_cockpit_against_latest_anchor(cockpit):
    chain = verify_audit_chain(cockpit)
    anchor = cockpit.audit_anchors.order_by("-anchored_sequence", "-id").first()
    if not anchor:
        return {"ok": False, "chain": chain, "anchor": None, "errors": ["no_external_anchor"]}
    details = verify_external_anchor(anchor, append_event=False)
    return {"ok": bool(chain["ok"] and details["ok"]), "chain": chain, "anchor": {
        "id": anchor.id, "provider": anchor.provider, "anchored_sequence": anchor.anchored_sequence,
        "anchored_head_hash": anchor.anchored_head_hash, "external_reference": anchor.external_reference,
        "receipt_hash": anchor.receipt_hash, "status": anchor.status,
    }, "anchor_verification": details, "errors": details.get("anchor_errors", [])}
