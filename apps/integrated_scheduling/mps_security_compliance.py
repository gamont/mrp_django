from __future__ import annotations
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import (
    MPSDecisionCockpit, MPSDecisionApprovalRequirement, MPSDecisionCompliancePolicy,
    MPSDecisionComplianceIncident, MPSDecisionComplianceSnapshot, MPSDecisionEvidenceExport,
)
from .mps_anchor_policy import protection_status, get_anchor_policy, ensure_required_anchors
from .mps_decision_audit import build_evidence_zip

DEFAULT_ALERT_STATUSES = ['STALE', 'UNPROTECTED', 'MISMATCH']


def get_compliance_policy(plant):
    policy, _ = MPSDecisionCompliancePolicy.objects.get_or_create(plant=plant)
    return policy


def cockpit_criticality(cockpit):
    req = cockpit.authority_requirements.exclude(status=MPSDecisionApprovalRequirement.Status.SUPERSEDED).order_by('-created_at').first()
    level = getattr(req, 'level', '')
    if level == 'EXECUTIVE_COMMITTEE':
        return 'CRITICAL'
    if level == 'DIRECTOR':
        return 'HIGH'
    return 'STANDARD'


def sla_hours_for(cockpit, policy):
    crit = cockpit_criticality(cockpit)
    return {
        'CRITICAL': policy.critical_sla_hours,
        'HIGH': policy.high_sla_hours,
        'STANDARD': policy.standard_sla_hours,
    }[crit]


def _severity_for(category, criticality):
    if category == 'MISMATCH':
        return MPSDecisionComplianceIncident.Severity.CRITICAL
    if criticality == 'CRITICAL':
        return MPSDecisionComplianceIncident.Severity.CRITICAL
    if criticality == 'HIGH' or category in {'UNPROTECTED', 'SLA_BREACH'}:
        return MPSDecisionComplianceIncident.Severity.HIGH
    return MPSDecisionComplianceIncident.Severity.MEDIUM


def _upsert_incident(cockpit, category, severity, message, details):
    now = timezone.now()
    incident = cockpit.compliance_incidents.filter(category=category, status__in=['OPEN', 'ACKNOWLEDGED']).order_by('-id').first()
    created = False
    if incident:
        incident.last_seen_at = now
        incident.severity = severity
        incident.message = message
        incident.details = details
        incident.save(update_fields=['last_seen_at','severity','message','details','updated_at'])
    else:
        incident = MPSDecisionComplianceIncident.objects.create(
            cockpit=cockpit, category=category, severity=severity, message=message, details=details,
            first_seen_at=now, last_seen_at=now,
        )
        created = True
    return incident, created


def _resolve_absent_incidents(cockpit, active_categories):
    now = timezone.now()
    qs = cockpit.compliance_incidents.filter(status__in=['OPEN','ACKNOWLEDGED']).exclude(category__in=active_categories)
    qs.update(status=MPSDecisionComplianceIncident.Status.RESOLVED, resolved_at=now, updated_at=now)


def evaluate_cockpit_compliance(cockpit, actor=None, remediate=True):
    plant = cockpit.publication.policy.plant
    policy = get_compliance_policy(plant)
    anchor_policy = get_anchor_policy(plant)
    if not policy.is_active:
        return {'cockpit_id': cockpit.id, 'skipped': True, 'reason': 'policy_inactive'}

    if remediate and cockpit.status == MPSDecisionCockpit.Status.FROZEN:
        ensure_required_anchors(cockpit, actor)

    protection = protection_status(cockpit, anchor_policy, verify=True)
    criticality = cockpit_criticality(cockpit)
    sla_hours = sla_hours_for(cockpit, policy)
    now = timezone.now()
    active = set()
    incidents = []

    state = protection['status']
    if state in {'STALE','UNPROTECTED','MISMATCH'}:
        active.add(state)
        inc, created = _upsert_incident(
            cockpit, state, _severity_for(state, criticality),
            f'Cockpit #{cockpit.id}: proteção externa em estado {state}.',
            {'protection': protection, 'criticality': criticality, 'sla_hours': sla_hours},
        )
        incidents.append((inc, created))

    first_anchor = cockpit.audit_anchors.order_by('anchored_at','id').first()
    origin = cockpit.frozen_at or cockpit.approved_at or cockpit.created_at
    if cockpit.status == MPSDecisionCockpit.Status.FROZEN and origin:
        elapsed = (first_anchor.anchored_at - origin) if first_anchor else (now - origin)
        if elapsed > timedelta(hours=sla_hours):
            active.add('SLA_BREACH')
            inc, created = _upsert_incident(
                cockpit, 'SLA_BREACH', _severity_for('SLA_BREACH', criticality),
                f'Cockpit #{cockpit.id}: SLA de ancoragem excedido ({sla_hours}h).',
                {'elapsed_minutes': round(elapsed.total_seconds()/60,2), 'sla_hours': sla_hours, 'criticality': criticality},
            )
            incidents.append((inc, created))

    last_export = cockpit.evidence_exports.order_by('-generated_at','-id').first()
    evidence_age = (now - last_export.generated_at) if last_export else None
    evidence_stale = (not last_export) or evidence_age > timedelta(hours=policy.evidence_max_age_hours)
    if cockpit.status == MPSDecisionCockpit.Status.FROZEN and evidence_stale:
        if remediate and policy.auto_export_evidence and protection['status'] == 'PROTECTED':
            build_evidence_zip(cockpit, actor)
            # Export is itself an audit event. Re-anchor the new chain head.
            ensure_required_anchors(cockpit, actor, force=True)
            last_export = cockpit.evidence_exports.order_by('-generated_at','-id').first()
            evidence_stale = False
        if evidence_stale:
            active.add('EVIDENCE_STALE')
            inc, created = _upsert_incident(
                cockpit, 'EVIDENCE_STALE', _severity_for('EVIDENCE_STALE', criticality),
                f'Cockpit #{cockpit.id}: pacote de evidências periódico está ausente ou vencido.',
                {'evidence_max_age_hours': policy.evidence_max_age_hours, 'last_export_at': getattr(last_export,'generated_at',None), 'criticality': criticality},
            )
            incidents.append((inc, created))

    _resolve_absent_incidents(cockpit, active)
    return {
        'cockpit_id': cockpit.id, 'criticality': criticality, 'sla_hours': sla_hours,
        'protection': protection, 'active_incidents': list(active),
        'new_incident_ids': [i.id for i, created in incidents if created],
    }


def _send_alerts(policy, incident_rows):
    if not policy.send_email_alerts or not policy.alert_recipients:
        return 0
    allowed = set(policy.alert_statuses or DEFAULT_ALERT_STATUSES + ['SLA_BREACH','EVIDENCE_STALE'])
    pending = [i for i in incident_rows if i.category in allowed and not i.alerted_at and i.status == 'OPEN']
    if not pending:
        return 0
    subject = f'[MRP] Security & Compliance · {policy.plant.code} · {len(pending)} alerta(s)'
    lines = [f'Planta: {policy.plant.code}', '', 'Alertas novos:']
    for i in pending:
        lines.append(f'- Cockpit #{i.cockpit_id} · {i.severity} · {i.category}: {i.message}')
    send_mail(subject, '\n'.join(lines), settings.DEFAULT_FROM_EMAIL, list(policy.alert_recipients), fail_silently=False)
    now = timezone.now()
    for i in pending:
        i.alerted_at = now
        i.save(update_fields=['alerted_at','updated_at'])
    return len(pending)


def build_compliance_snapshot(plant, rows=None):
    now = timezone.now()
    policy = get_compliance_policy(plant)
    if rows is None:
        qs = MPSDecisionCockpit.objects.select_related('publication__policy__plant').filter(publication__policy__plant=plant).exclude(status=MPSDecisionCockpit.Status.REJECTED)
        rows = [evaluate_cockpit_compliance(c, remediate=False) for c in qs]
    monitored = len(rows)
    counts = {'PROTECTED':0,'STALE':0,'UNPROTECTED':0,'MISMATCH':0}
    current_evidence = 0
    first_anchor_minutes=[]
    for row in rows:
        if row.get('skipped'): continue
        counts[row['protection']['status']] = counts.get(row['protection']['status'],0)+1
        c = MPSDecisionCockpit.objects.get(pk=row['cockpit_id'])
        e = c.evidence_exports.order_by('-generated_at').first()
        if e and now-e.generated_at <= timedelta(hours=policy.evidence_max_age_hours): current_evidence += 1
        a = c.audit_anchors.order_by('anchored_at').first(); origin=c.frozen_at or c.approved_at or c.created_at
        if a and origin and a.anchored_at >= origin: first_anchor_minutes.append((a.anchored_at-origin).total_seconds()/60)
    protected_pct = Decimal(str(round((counts['PROTECTED']/monitored*100) if monitored else 0,2)))
    evidence_pct = Decimal(str(round((current_evidence/monitored*100) if monitored else 0,2)))
    avg_anchor = Decimal(str(round(sum(first_anchor_minutes)/len(first_anchor_minutes),2))) if first_anchor_minutes else Decimal('0')
    open_incidents=MPSDecisionComplianceIncident.objects.filter(cockpit__publication__policy__plant=plant,status__in=['OPEN','ACKNOWLEDGED']).count()
    snap,_=MPSDecisionComplianceSnapshot.objects.update_or_create(
        plant=plant,snapshot_date=now.date(),defaults={
            'monitored_count':monitored,'protected_count':counts['PROTECTED'],'stale_count':counts['STALE'],
            'unprotected_count':counts['UNPROTECTED'],'mismatch_count':counts['MISMATCH'],'protected_percent':protected_pct,
            'evidence_current_percent':evidence_pct,'avg_minutes_to_first_anchor':avg_anchor,
            'integrity_failures':counts['MISMATCH'],'open_incidents':open_incidents,
            'details':{'evidence_current_count':current_evidence,'first_anchor_sample_count':len(first_anchor_minutes)},
        })
    return snap


def run_security_compliance(actor=None, remediate=True):
    results=[]
    for policy in MPSDecisionCompliancePolicy.objects.select_related('plant').filter(is_active=True):
        qs=MPSDecisionCockpit.objects.select_related('publication__policy__plant').filter(publication__policy__plant=policy.plant).exclude(status=MPSDecisionCockpit.Status.REJECTED)
        plant_rows=[]
        for c in qs:
            row=evaluate_cockpit_compliance(c,actor,remediate=remediate); results.append(row); plant_rows.append(row)
        incidents=list(MPSDecisionComplianceIncident.objects.filter(cockpit__publication__policy__plant=policy.plant,status='OPEN'))
        alerts=_send_alerts(policy,incidents)
        snap=build_compliance_snapshot(policy.plant,plant_rows)
        results.append({'plant':policy.plant.code,'snapshot_id':snap.id,'alerts_sent':alerts,'summary':True})
    return results


def compliance_dashboard():
    rows=[]
    qs=MPSDecisionCockpit.objects.select_related('publication__policy__plant').exclude(status=MPSDecisionCockpit.Status.REJECTED)
    for c in qs:
        plant=c.publication.policy.plant; p=get_compliance_policy(plant)
        protection=protection_status(c,get_anchor_policy(plant),verify=False)
        rows.append({'cockpit':c,'plant':plant,'criticality':cockpit_criticality(c),'sla_hours':sla_hours_for(c,p),'protection':protection,
                     'open_incidents':list(c.compliance_incidents.filter(status__in=['OPEN','ACKNOWLEDGED']).order_by('-severity','-last_seen_at'))})
    severity={'MISMATCH':0,'UNPROTECTED':1,'STALE':2,'PROTECTED':3}
    rows.sort(key=lambda r:(severity.get(r['protection']['status'],9),-r['cockpit'].id))
    latest=list(MPSDecisionComplianceSnapshot.objects.select_related('plant').order_by('plant__code','-snapshot_date'))
    seen=set(); snapshots=[]
    for s in latest:
        if s.plant_id not in seen: snapshots.append(s); seen.add(s.plant_id)
    return rows,snapshots
