from __future__ import annotations
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from .models import (
    MPSDecisionCockpit, MPSDecisionCandidateReview,
    MPSRevisionOptimizationRun, MPSRevisionOptimizationCandidate,
    MPSRevision, MPSRevisionSimulation,
)


def _user_id(user):
    return getattr(user, "id", None) if user else None


def _candidate_snapshot(candidate):
    sim = candidate.simulation
    financing = ((sim.financial_summary or {}).get("financing_087", {}) if sim else {})
    return {
        "candidate_id": candidate.id,
        "name": candidate.name,
        "strategy": candidate.strategy,
        "rank": candidate.rank,
        "pareto_rank": candidate.pareto_rank,
        "is_pareto": candidate.is_pareto,
        "score": str(candidate.score) if candidate.score is not None else None,
        "objective_vector": candidate.objective_vector or {},
        "metrics": candidate.metrics or {},
        "financially_feasible": financing.get("financially_feasible", {}).get("right") if financing else None,
        "simulation_id": sim.id if sim else None,
    }


@transaction.atomic
def create_decision_cockpit(optimization_run, user=None):
    run = MPSRevisionOptimizationRun.objects.select_for_update().select_related("revision__publication", "compare_revision").get(pk=optimization_run.pk)
    if run.status != MPSRevisionOptimizationRun.Status.COMPLETED:
        raise ValueError("O cockpit só pode ser criado para uma otimização concluída.")
    if not run.candidates.exists():
        raise ValueError("A otimização não possui candidatos.")
    obj, created = MPSDecisionCockpit.objects.get_or_create(
        optimization_run=run,
        defaults={"publication": run.revision.publication, "baseline_revision": run.compare_revision, "created_by": user},
    )
    if created:
        MPSDecisionCandidateReview.objects.bulk_create([
            MPSDecisionCandidateReview(cockpit=obj, candidate=c, shortlisted=bool(c.is_pareto), priority=c.rank or 0)
            for c in run.candidates.all()
        ])
    if created:
        from .mps_decision_audit import append_audit_event
        append_audit_event(obj, "COCKPIT_CREATED", user, {"optimization_run_id": run.id, "baseline_revision_id": run.compare_revision_id})
    return obj


@transaction.atomic
def review_candidate(cockpit, candidate, user=None, shortlisted=None, business_label=None, executive_note=None, priority=None):
    cockpit = MPSDecisionCockpit.objects.select_for_update().get(pk=cockpit.pk)
    if cockpit.status in [MPSDecisionCockpit.Status.FROZEN, MPSDecisionCockpit.Status.REJECTED]:
        raise ValueError("Cockpit encerrado; as avaliações não podem mais ser alteradas.")
    if candidate.optimization_run_id != cockpit.optimization_run_id:
        raise ValueError("Candidato não pertence à otimização deste cockpit.")
    row, _ = MPSDecisionCandidateReview.objects.get_or_create(cockpit=cockpit, candidate=candidate)
    if shortlisted is not None: row.shortlisted = bool(shortlisted)
    if business_label is not None: row.business_label = business_label[:120]
    if executive_note is not None: row.executive_note = executive_note
    if priority is not None: row.priority = max(0, int(priority))
    row.reviewed_by = user; row.reviewed_at = timezone.now(); row.save()
    return row


@transaction.atomic
def select_candidate(cockpit, candidate, user=None, rationale=""):
    cockpit = MPSDecisionCockpit.objects.select_for_update().get(pk=cockpit.pk)
    if cockpit.status not in [MPSDecisionCockpit.Status.OPEN, MPSDecisionCockpit.Status.SELECTED]:
        raise ValueError("O cockpit não está aberto para seleção.")
    if candidate.optimization_run_id != cockpit.optimization_run_id:
        raise ValueError("Candidato não pertence a este cockpit.")
    if not (rationale or "").strip():
        raise ValueError("Informe a justificativa para a seleção do cenário.")
    if not candidate.simulation_id or candidate.simulation.status != MPSRevisionSimulation.Status.COMPLETED:
        raise ValueError("O cenário precisa ter uma simulação completa antes da seleção executiva.")
    cockpit.selected_candidate = candidate
    cockpit.selection_rationale = rationale
    cockpit.selected_by = user
    cockpit.selected_at = timezone.now()
    cockpit.status = MPSDecisionCockpit.Status.SELECTED
    cockpit.decision_snapshot = {"selected": _candidate_snapshot(candidate), "selected_at": cockpit.selected_at.isoformat()}
    cockpit.save()
    from .mps_decision_audit import append_audit_event
    append_audit_event(cockpit, "CANDIDATE_SELECTED", user, {"candidate_id": candidate.id, "rationale": rationale, "objective_vector": candidate.objective_vector or {}})
    append_audit_event(cockpit, "SIMULATION_REFERENCED", user, {"candidate_id": candidate.id, "simulation_id": candidate.simulation_id, "simulation_status": candidate.simulation.status, "simulation_summary": candidate.simulation.summary or {}, "financial_summary": candidate.simulation.financial_summary or {}})
    return cockpit


@transaction.atomic
def submit_decision(cockpit, user=None):
    cockpit = MPSDecisionCockpit.objects.select_for_update().get(pk=cockpit.pk)
    if cockpit.status != MPSDecisionCockpit.Status.SELECTED or not cockpit.selected_candidate_id:
        raise ValueError("Selecione um cenário antes de enviar para aprovação.")
    from .mps_decision_governance import initialize_governance
    initialize_governance(cockpit, user)
    from .mps_decision_authority import initialize_authority_requirements
    initialize_authority_requirements(cockpit)
    cockpit.status = MPSDecisionCockpit.Status.PENDING_APPROVAL
    cockpit.submitted_by = user; cockpit.submitted_at = timezone.now(); cockpit.save()
    from .mps_decision_audit import append_audit_event
    append_audit_event(cockpit, "SUBMITTED", user, {"selected_candidate_id": cockpit.selected_candidate_id})
    return cockpit


@transaction.atomic
def approve_decision(cockpit, user=None, notes=""):
    cockpit = MPSDecisionCockpit.objects.select_for_update(of=("self",)).select_related("selected_candidate__simulation").get(pk=cockpit.pk)
    if cockpit.status != MPSDecisionCockpit.Status.PENDING_APPROVAL:
        raise ValueError("A decisão não está aguardando aprovação.")
    if _user_id(user) and cockpit.selected_by_id and _user_id(user) == cockpit.selected_by_id:
        raise ValueError("Quem selecionou o cenário não pode aprovar a própria decisão executiva.")
    from .mps_decision_governance import governance_check, formal_minutes_snapshot
    check = governance_check(cockpit)
    if not check["ok"]:
        raise ValueError("Governança 0.9.1 bloqueou a aprovação: " + " ".join(check["blockers"]))
    from .mps_decision_authority import authority_check
    auth_check = authority_check(cockpit)
    if not auth_check['ok']:
        raise ValueError('Alçada 0.9.2 bloqueou a aprovação: ' + ' '.join(auth_check['blockers']))
    c = cockpit.selected_candidate
    if not c or not c.simulation_id or c.simulation.status != MPSRevisionSimulation.Status.COMPLETED:
        raise ValueError("O cenário selecionado não possui simulação concluída.")
    cockpit.status = MPSDecisionCockpit.Status.APPROVED
    cockpit.approved_by = user; cockpit.approved_at = timezone.now(); cockpit.executive_notes = notes
    snap = dict(cockpit.decision_snapshot or {}); snap["approval"] = {"approved_at": cockpit.approved_at.isoformat(), "approved_by_id": _user_id(user), "notes": notes}; snap["formal_minutes_091"] = formal_minutes_snapshot(cockpit); snap["authority_092"] = auth_check
    cockpit.decision_snapshot = snap; cockpit.save()
    from .mps_decision_audit import append_audit_event
    append_audit_event(cockpit, "EXECUTIVE_APPROVED", user, {"candidate_id": cockpit.selected_candidate_id, "notes": notes, "authority": auth_check})
    return cockpit


@transaction.atomic
def reject_decision(cockpit, user=None, notes=""):
    cockpit = MPSDecisionCockpit.objects.select_for_update().get(pk=cockpit.pk)
    if cockpit.status != MPSDecisionCockpit.Status.PENDING_APPROVAL:
        raise ValueError("A decisão não está aguardando aprovação.")
    cockpit.status = MPSDecisionCockpit.Status.REJECTED
    cockpit.approved_by = user; cockpit.approved_at = timezone.now(); cockpit.executive_notes = notes; cockpit.save()
    from .mps_decision_audit import append_audit_event
    append_audit_event(cockpit, "EXECUTIVE_REJECTED", user, {"notes": notes})
    return cockpit


@transaction.atomic
def freeze_selected_as_official(cockpit, user=None):
    """Materializa o cenário aprovado no MPS e cria uma revisão oficial APPROVED.

    Não publica o MasterProductionSchedule nem executa MRP; essas ações permanecem
    separadas e continuam sujeitas ao RCCP e ao workflow da publicação.
    """
    cockpit = MPSDecisionCockpit.objects.select_for_update(of=("self",)).select_related("selected_candidate", "approved_by", "selected_by").get(pk=cockpit.pk)
    if cockpit.status != MPSDecisionCockpit.Status.APPROVED:
        raise ValueError("Somente uma decisão executiva APPROVED pode ser congelada.")
    candidate = cockpit.selected_candidate
    raw = (candidate.planning_overrides or {}).get("candidate_mps_lines") if candidate else None
    if not raw:
        raise ValueError("O cenário selecionado não contém buckets MPS aplicáveis; recomendações somente de sourcing não podem ser congeladas como MPS.")
    if not candidate.simulation_id or candidate.simulation.status != MPSRevisionSimulation.Status.COMPLETED:
        raise ValueError("A simulação do cenário selecionado precisa estar concluída.")

    from .mps_optimizer import adopt_candidate
    # O autor operacional é quem selecionou o cenário; a aprovação executiva já ocorreu no cockpit.
    rev = adopt_candidate(candidate, cockpit.selected_by, f"Cockpit executivo #{cockpit.id}: {cockpit.selection_rationale}")
    # A aprovação do cockpit é a trilha de governança para esta materialização.
    rev.publication.revisions.filter(status=MPSRevision.Status.APPROVED).exclude(pk=rev.pk).update(status=MPSRevision.Status.SUPERSEDED)
    rev.status = MPSRevision.Status.APPROVED
    rev.submitted_by = cockpit.submitted_by
    rev.submitted_at = cockpit.submitted_at
    rev.approved_by = cockpit.approved_by
    rev.approved_at = cockpit.approved_at or timezone.now()
    rev.decision_notes = f"Aprovada via cockpit 0.9.0 #{cockpit.id}. {cockpit.executive_notes}".strip()
    rev.label = (rev.label + f" · OFFICIAL cockpit #{cockpit.id}")[:160]
    rev.save(update_fields=["status","submitted_by","submitted_at","approved_by","approved_at","decision_notes","label","updated_at"])

    cockpit.official_revision = rev
    cockpit.status = MPSDecisionCockpit.Status.FROZEN
    cockpit.frozen_by = user; cockpit.frozen_at = timezone.now()
    snap = dict(cockpit.decision_snapshot or {}); snap["freeze"] = {"official_revision_id": rev.id, "revision_number": rev.number, "frozen_at": cockpit.frozen_at.isoformat(), "frozen_by_id": _user_id(user)}
    cockpit.decision_snapshot = snap; cockpit.save()
    from .mps_decision_audit import append_audit_event
    append_audit_event(cockpit, "OFFICIAL_FROZEN", user, {"official_revision_id": rev.id, "revision_number": rev.number})
    # 0.9.5: anchor automatically after the freeze transaction commits when policy requests it.
    def _anchor_after_commit():
        from .models import MPSDecisionCockpit, MPSDecisionAnchorPolicy
        from .mps_anchor_policy import ensure_required_anchors
        fresh=MPSDecisionCockpit.objects.select_related("publication__policy__plant").get(pk=cockpit.pk)
        policy=getattr(fresh.publication.policy.plant,"mps_decision_anchor_policy",None)
        if policy and policy.is_active and policy.cadence in {MPSDecisionAnchorPolicy.Cadence.ON_FREEZE,MPSDecisionAnchorPolicy.Cadence.BOTH}:
            ensure_required_anchors(fresh,user,force=True)
    transaction.on_commit(_anchor_after_commit)
    return cockpit


def candidate_comparison(cockpit, left_id=None, right_id=None):
    qs = cockpit.optimization_run.candidates.select_related("simulation").all()
    by_id = {x.id: x for x in qs}
    left = by_id.get(int(left_id)) if left_id else None
    right = by_id.get(int(right_id)) if right_id else None
    if not left or not right:
        pareto = sorted(qs, key=lambda c: (c.pareto_rank or 9999, c.rank or 9999, c.id))
        left = left or (pareto[0] if pareto else None)
        right = right or (pareto[1] if len(pareto) > 1 else left)
    return {"left": _candidate_snapshot(left) if left else None, "right": _candidate_snapshot(right) if right else None}
