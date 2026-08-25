from django.db import transaction
from django.utils import timezone
from .models import (MPSDecisionGovernancePolicy,MPSDecisionMeeting,MPSDecisionParticipant,MPSDecisionAreaApproval,MPSDecisionRiskAcceptance,MPSDecisionCondition,MPSDecisionCockpit)

def policy_for(cockpit):
    plant=cockpit.publication.cycle.plant
    p,_=MPSDecisionGovernancePolicy.objects.get_or_create(plant=plant,defaults={'required_areas':MPSDecisionGovernancePolicy.DEFAULT_AREAS})
    return p

@transaction.atomic
def initialize_governance(cockpit,user=None):
    p=policy_for(cockpit)
    meeting,_=MPSDecisionMeeting.objects.get_or_create(cockpit=cockpit,defaults={'meeting_at':timezone.now(),'minute_number':f'MPS-{cockpit.id:06d}'})
    for area in p.effective_required_areas():
        MPSDecisionAreaApproval.objects.get_or_create(cockpit=cockpit,area=area,defaults={'is_required':True})
    return meeting

@transaction.atomic
def record_area_decision(cockpit,area,decision,user=None,comment=''):
    initialize_governance(cockpit,user)
    row=MPSDecisionAreaApproval.objects.select_for_update().get(cockpit=cockpit,area=area)
    if cockpit.status not in [MPSDecisionCockpit.Status.SELECTED,MPSDecisionCockpit.Status.PENDING_APPROVAL]:
        raise ValueError('O cockpit precisa estar selecionado ou aguardando aprovação.')
    if decision not in MPSDecisionAreaApproval.Decision.values: raise ValueError('Decisão inválida.')
    row.decision=decision; row.approver=user; row.decided_at=timezone.now(); row.comment=comment; row.save()
    from .mps_decision_audit import append_audit_event
    append_audit_event(cockpit, "AREA_DECISION", user, {"area": area, "decision": decision, "comment": comment, "approval_id": row.id})
    return row

def governance_check(cockpit):
    p=policy_for(cockpit); initialize_governance(cockpit)
    blockers=[]
    meeting=getattr(cockpit,'meeting',None)
    if meeting and meeting.participants.filter(attended=True).count() < p.minimum_participants:
        blockers.append(f'Participantes presentes abaixo do mínimo ({p.minimum_participants}).')
    if p.require_area_approvals:
        pending=list(cockpit.area_approvals.filter(is_required=True).exclude(decision=MPSDecisionAreaApproval.Decision.APPROVED).values_list('area',flat=True))
        if pending: blockers.append('Áreas sem aprovação: '+', '.join(pending)+'.')
    if p.require_risk_acceptance and cockpit.risk_acceptances.filter(status=MPSDecisionRiskAcceptance.Status.OPEN).exists():
        blockers.append('Existem riscos ainda abertos sem aceite ou mitigação.')
    if p.require_conditions_closed and cockpit.approval_conditions.filter(status=MPSDecisionCondition.Status.OPEN).exists():
        blockers.append('Existem condições de aprovação ainda abertas.')
    return {'ok':not blockers,'blockers':blockers,'policy_id':p.id}

def formal_minutes_snapshot(cockpit):
    meeting=getattr(cockpit,'meeting',None)
    return {'cockpit_id':cockpit.id,'status':cockpit.status,'selection_rationale':cockpit.selection_rationale,'executive_notes':cockpit.executive_notes,
      'meeting':({'minute_number':meeting.minute_number,'meeting_at':meeting.meeting_at.isoformat() if meeting.meeting_at else None,'location':meeting.location,'agenda':meeting.agenda,'minutes':meeting.minutes,'conclusion':meeting.conclusion} if meeting else None),
      'participants':list(meeting.participants.values('name','area','role_title','attended','is_decision_maker')) if meeting else [],
      'area_approvals':list(cockpit.area_approvals.values('area','is_required','decision','approver_id','decided_at','comment')),
      'risks':list(cockpit.risk_acceptances.values('category','description','impact','mitigation','status','owner_id','accepted_by_id')),
      'conditions':list(cockpit.approval_conditions.values('description','due_date','status','owner_id')),
      'comments':list(cockpit.formal_comments.values('author_id','area','text','is_resolved','created_at'))}
