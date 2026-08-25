from __future__ import annotations
from datetime import timedelta
from django.utils import timezone
from .models import MPSDecisionAnchorPolicy, MPSDecisionAuditAnchor, MPSDecisionCockpit
from .mps_decision_anchor import publish_external_anchor, verify_external_anchor
from .mps_decision_audit import verify_audit_chain

PROTECTED='PROTECTED'; STALE='STALE'; UNPROTECTED='UNPROTECTED'; MISMATCH='MISMATCH'

def get_anchor_policy(plant):
    policy,_=MPSDecisionAnchorPolicy.objects.get_or_create(plant=plant,defaults={
        'required_providers':[MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY],
    })
    if not policy.required_providers:
        policy.required_providers=[MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY]
        policy.save(update_fields=['required_providers','updated_at'])
    return policy

def cockpit_plant(cockpit):
    return cockpit.publication.policy.plant

def protection_status(cockpit, policy=None, verify=False):
    policy=policy or get_anchor_policy(cockpit_plant(cockpit))
    chain=verify_audit_chain(cockpit)
    required=list(policy.required_providers or [MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY])
    now=timezone.now(); details=[]; worst=PROTECTED
    if not chain['ok']:
        return {'status':MISMATCH,'chain_ok':False,'providers':details,'head_hash':chain.get('head_hash'),'event_count':chain.get('event_count',0)}
    for provider in required:
        anchor=cockpit.audit_anchors.filter(provider=provider).order_by('-anchored_sequence','-id').first()
        if not anchor:
            details.append({'provider':provider,'status':UNPROTECTED,'anchor_id':None}); worst=UNPROTECTED; continue
        ok=True
        if verify:
            ok=verify_external_anchor(anchor,append_event=False).get('ok',False)
        elif anchor.status == MPSDecisionAuditAnchor.Status.MISMATCH:
            ok=False
        age=now-anchor.anchored_at
        status=PROTECTED
        if not ok: status=MISMATCH
        elif age > timedelta(hours=policy.max_anchor_age_hours): status=STALE
        details.append({'provider':provider,'status':status,'anchor_id':anchor.id,'anchored_at':anchor.anchored_at,'anchored_sequence':anchor.anchored_sequence})
        if status==MISMATCH: worst=MISMATCH
        elif status==UNPROTECTED and worst!=MISMATCH: worst=UNPROTECTED
        elif status==STALE and worst==PROTECTED: worst=STALE
    return {'status':worst,'chain_ok':True,'providers':details,'head_hash':chain.get('head_hash'),'event_count':chain.get('event_count',0),'max_anchor_age_hours':policy.max_anchor_age_hours}

def ensure_required_anchors(cockpit, actor=None, force=False):
    policy=get_anchor_policy(cockpit_plant(cockpit))
    created=[]
    for provider in policy.required_providers or [MPSDecisionAuditAnchor.Provider.FILE_APPEND_ONLY]:
        latest=cockpit.audit_anchors.filter(provider=provider).order_by('-anchored_sequence','-id').first()
        stale=(not latest) or (timezone.now()-latest.anchored_at > timedelta(hours=policy.max_anchor_age_hours))
        chain=verify_audit_chain(cockpit)
        behind=(not latest) or latest.anchored_sequence < chain['event_count']
        if force or stale or behind:
            if provider == MPSDecisionAuditAnchor.Provider.MANUAL_EXTERNAL:
                continue
            a=publish_external_anchor(cockpit,actor,provider=provider)
            if policy.verify_after_publish: verify_external_anchor(a,actor,append_event=False)
            created.append(a)
    return created, protection_status(cockpit,policy,verify=True)

def run_anchor_policy(actor=None):
    rows=[]
    for policy in MPSDecisionAnchorPolicy.objects.select_related('plant').filter(is_active=True):
        if policy.cadence not in {MPSDecisionAnchorPolicy.Cadence.DAILY,MPSDecisionAnchorPolicy.Cadence.BOTH}:
            continue
        qs=MPSDecisionCockpit.objects.select_related('publication__policy__plant').filter(publication__policy__plant=policy.plant)
        if not policy.protect_active_cockpits:
            qs=qs.filter(status=MPSDecisionCockpit.Status.FROZEN)
        else:
            qs=qs.exclude(status=MPSDecisionCockpit.Status.REJECTED)
        for cockpit in qs:
            created,status=ensure_required_anchors(cockpit,actor)
            rows.append({'cockpit_id':cockpit.id,'created':[a.id for a in created],'status':status['status']})
    return rows

def protection_dashboard():
    rows=[]
    qs=MPSDecisionCockpit.objects.select_related('publication__policy__plant').exclude(status=MPSDecisionCockpit.Status.REJECTED)
    for c in qs:
        p=get_anchor_policy(c.publication.policy.plant)
        s=protection_status(c,p,verify=False)
        rows.append({'cockpit':c,'plant':c.publication.policy.plant,'policy':p,'protection':s})
    order={MISMATCH:0,UNPROTECTED:1,STALE:2,PROTECTED:3}
    rows.sort(key=lambda x:(order.get(x['protection']['status'],9),-x['cockpit'].id))
    return rows
