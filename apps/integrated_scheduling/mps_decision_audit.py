from __future__ import annotations
import hashlib, io, json, zipfile
from pathlib import Path
from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from .models import MPSDecisionAuditEvent, MPSDecisionEvidenceExport, MPSDecisionAuditAnchor

GENESIS = "0" * 64


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _event_hash(cockpit_id, sequence, event_type, occurred_at, actor_username, payload, previous_hash):
    body = {
        "cockpit_id": cockpit_id,
        "sequence": sequence,
        "event_type": event_type,
        "occurred_at": occurred_at.isoformat(),
        "actor_username": actor_username or "",
        "payload": payload or {},
        "previous_hash": previous_hash or GENESIS,
        "hash_algorithm": "SHA256",
    }
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


@transaction.atomic
def append_audit_event(cockpit, event_type, actor=None, payload=None, occurred_at=None):
    from .models import MPSDecisionCockpit
    locked = MPSDecisionCockpit.objects.select_for_update().get(pk=cockpit.pk)
    last = locked.audit_events.order_by("-sequence").first()
    sequence = (last.sequence if last else 0) + 1
    previous_hash = last.event_hash if last else GENESIS
    occurred_at = occurred_at or timezone.now()
    username = actor.get_username() if actor and getattr(actor, "is_authenticated", False) else ""
    payload = payload or {}
    event_hash = _event_hash(locked.id, sequence, event_type, occurred_at, username, payload, previous_hash)
    return MPSDecisionAuditEvent.objects.create(
        cockpit=locked, sequence=sequence, event_type=event_type, occurred_at=occurred_at,
        actor=actor if actor and getattr(actor, "is_authenticated", False) else None,
        actor_username=username, payload=payload, previous_hash=previous_hash, event_hash=event_hash,
    )


def verify_audit_chain(cockpit):
    events = list(cockpit.audit_events.order_by("sequence"))
    previous = GENESIS
    errors = []
    expected_sequence = 1
    for e in events:
        if e.sequence != expected_sequence:
            errors.append({"sequence": e.sequence, "error": f"sequence_gap_expected_{expected_sequence}"})
        if e.previous_hash != previous:
            errors.append({"sequence": e.sequence, "error": "previous_hash_mismatch"})
        expected = _event_hash(e.cockpit_id, e.sequence, e.event_type, e.occurred_at, e.actor_username, e.payload, e.previous_hash)
        if expected != e.event_hash:
            errors.append({"sequence": e.sequence, "error": "event_hash_mismatch"})
        previous = e.event_hash
        expected_sequence += 1
    return {"ok": not errors, "event_count": len(events), "head_hash": previous if events else GENESIS, "errors": errors}


def _signature_rows(cockpit):
    rows=[]
    for req in cockpit.authority_requirements.prefetch_related("signatures__signer").all():
        for s in req.signatures.all():
            rows.append({
                "requirement_id": req.id, "level": req.level, "signer": s.signer_username,
                "signed_at": s.signed_at.isoformat(), "authentication_method": s.authentication_method,
                "content_hash": s.content_hash, "signature_hash": s.signature_hash,
                "signature_version": s.signature_version,
            })
    return rows


def evidence_manifest(cockpit):
    verification = verify_audit_chain(cockpit)
    meeting = getattr(cockpit, "meeting", None)
    data = {
        "schema": "MRP-MPS-EVIDENCE-0.9.4",
        "generated_at": timezone.now().isoformat(),
        "cockpit": {
            "id": cockpit.id, "status": cockpit.status, "publication_id": cockpit.publication_id,
            "optimization_run_id": cockpit.optimization_run_id, "baseline_revision_id": cockpit.baseline_revision_id,
            "selected_candidate_id": cockpit.selected_candidate_id, "official_revision_id": cockpit.official_revision_id,
            "selection_rationale": cockpit.selection_rationale, "executive_notes": cockpit.executive_notes,
            "decision_snapshot": cockpit.decision_snapshot,
        },
        "meeting": ({
            "minute_number": meeting.minute_number, "title": meeting.title,
            "meeting_at": meeting.meeting_at.isoformat() if meeting.meeting_at else None,
            "location": meeting.location, "agenda": meeting.agenda, "minutes": meeting.minutes,
            "conclusion": meeting.conclusion, "closed_at": meeting.closed_at.isoformat() if meeting.closed_at else None,
        } if meeting else None),
        "audit_verification": verification,
        "electronic_signatures": _signature_rows(cockpit),
        "external_anchors": [{"id":a.id,"provider":a.provider,"anchored_sequence":a.anchored_sequence,"anchored_head_hash":a.anchored_head_hash,"anchored_at":a.anchored_at.isoformat(),"external_reference":a.external_reference,"receipt_hash":a.receipt_hash,"status":a.status} for a in cockpit.audit_anchors.all()],
    }
    return data


def build_evidence_zip(cockpit, actor=None):
    # Add export event first so the exported chain proves that an export occurred.
    append_audit_event(cockpit, MPSDecisionAuditEvent.EventType.EVIDENCE_EXPORTED, actor, {"format": "ZIP", "schema": "MRP-MPS-EVIDENCE-0.9.4"})
    cockpit.refresh_from_db()
    manifest = evidence_manifest(cockpit)
    events = [{
        "sequence": e.sequence, "event_type": e.event_type, "occurred_at": e.occurred_at.isoformat(),
        "actor_username": e.actor_username, "payload": e.payload, "previous_hash": e.previous_hash,
        "event_hash": e.event_hash, "hash_algorithm": e.hash_algorithm,
    } for e in cockpit.audit_events.order_by("sequence")]
    signatures = manifest["electronic_signatures"]
    buf=io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
        z.writestr("audit_chain.json", json.dumps(events, indent=2, ensure_ascii=False, default=str))
        z.writestr("electronic_signatures.json", json.dumps(signatures, indent=2, ensure_ascii=False, default=str))
        z.writestr("decision_snapshot.json", json.dumps(cockpit.decision_snapshot or {}, indent=2, ensure_ascii=False, default=str))
        z.writestr("external_anchors.json", json.dumps(manifest.get("external_anchors", []), indent=2, ensure_ascii=False, default=str))
        # Attach user-uploaded evidence if storage exposes a local file path.
        attachments=[]
        for a in cockpit.attachments_091.all():
            row={"id":a.id,"title":getattr(a,"title","")}
            f=getattr(a,"file",None)
            try:
                p=Path(f.path)
                if p.is_file():
                    raw=p.read_bytes(); sha=hashlib.sha256(raw).hexdigest(); arc=f"attachments/{a.id}_{p.name}"
                    z.writestr(arc,raw); row.update({"file":arc,"sha256":sha,"size":len(raw)})
            except Exception as exc:
                row["not_embedded"] = str(exc)
            attachments.append(row)
        z.writestr("attachments_manifest.json", json.dumps(attachments, indent=2, ensure_ascii=False, default=str))
    raw=buf.getvalue(); sha=hashlib.sha256(raw).hexdigest()
    filename=f"mps_decision_evidence_cockpit_{cockpit.id}_{timezone.now().strftime('%Y%m%dT%H%M%S')}.zip"
    v=manifest["audit_verification"]
    MPSDecisionEvidenceExport.objects.create(cockpit=cockpit,generated_by=actor if actor and getattr(actor,'is_authenticated',False) else None,audit_head_hash=v['head_hash'],audit_event_count=v['event_count'],verification_ok=v['ok'],manifest=manifest,package_sha256=sha,file_name=filename)
    return filename, raw, sha, manifest
