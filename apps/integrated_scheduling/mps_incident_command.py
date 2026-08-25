from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from .models import (
    MPSComplianceEscalationEvent,
    MPSDecisionComplianceIncident,
    MPSIncidentCommandPolicy,
    MPSMajorIncident,
    MPSMajorIncidentAction,
    MPSMajorIncidentLearningAction,
    MPSMajorIncidentPostmortem,
    MPSMajorIncidentTimelineEvent,
)


def _major_severity(compliance_incident):
    return {
        'CRITICAL': MPSMajorIncident.Severity.SEV1,
        'HIGH': MPSMajorIncident.Severity.SEV2,
        'MEDIUM': MPSMajorIncident.Severity.SEV3,
        'LOW': MPSMajorIncident.Severity.SEV4,
    }.get(compliance_incident.severity, MPSMajorIncident.Severity.SEV3)


def _next_code(plant, now=None):
    now = now or timezone.now()
    prefix = f"MI-{plant.code}-{now:%Y%m%d}"
    n = MPSMajorIncident.objects.filter(code__startswith=prefix).count() + 1
    return f"{prefix}-{n:03d}"


@transaction.atomic
def promote_compliance_incident(compliance_incident, actor=None, title=''):
    existing = compliance_incident.major_incidents.filter(status__in=[
        MPSMajorIncident.Status.DETECTED,
        MPSMajorIncident.Status.ACTIVE,
        MPSMajorIncident.Status.MONITORING,
    ]).first()
    if existing:
        return existing, False
    plant = compliance_incident.cockpit.publication.policy.plant
    major = MPSMajorIncident.objects.create(
        plant=plant,
        code=_next_code(plant),
        title=title or f"{compliance_incident.get_category_display()} · Cockpit #{compliance_incident.cockpit_id}",
        severity=_major_severity(compliance_incident),
        status=MPSMajorIncident.Status.ACTIVE,
        commander=actor,
        acknowledged_at=timezone.now() if actor else None,
        summary=compliance_incident.message,
        details={'source':'MPS_COMPLIANCE','compliance_incident_id':compliance_incident.id},
    )
    major.compliance_incidents.add(compliance_incident)
    MPSMajorIncidentTimelineEvent.objects.create(
        incident=major,
        event_type=MPSMajorIncidentTimelineEvent.EventType.DETECTED,
        actor=actor,
        message=f"Incidente maior criado a partir do incidente de compliance #{compliance_incident.id}.",
        details={'compliance_category':compliance_incident.category,'compliance_severity':compliance_incident.severity},
    )
    return major, True


def maybe_auto_promote(compliance_incident, escalation_level, actor=None):
    plant = compliance_incident.cockpit.publication.policy.plant
    policy = MPSIncidentCommandPolicy.objects.filter(plant=plant, is_active=True).first()
    if not policy:
        return None
    levels = policy.auto_promote_levels or ['EXECUTIVE']
    severities = policy.auto_promote_severities or ['CRITICAL']
    if escalation_level not in levels or compliance_incident.severity not in severities:
        return None
    major, created = promote_compliance_incident(compliance_incident, actor=actor)
    if created:
        MPSMajorIncidentTimelineEvent.objects.create(
            incident=major,
            event_type=MPSMajorIncidentTimelineEvent.EventType.ESCALATION,
            actor=actor,
            message=f"Promoção automática por escalonamento {escalation_level}.",
            details={'escalation_level':escalation_level},
        )
    return major


@transaction.atomic
def add_timeline_event(incident, message, event_type='UPDATE', actor=None, details=None):
    return MPSMajorIncidentTimelineEvent.objects.create(
        incident=incident, message=message, event_type=event_type, actor=actor, details=details or {}
    )


@transaction.atomic
def resolve_major_incident(incident, actor=None, summary=''):
    if incident.status == MPSMajorIncident.Status.CLOSED:
        raise ValueError('Incidente já está encerrado.')
    incident.status = MPSMajorIncident.Status.RESOLVED
    incident.resolved_at = timezone.now()
    if summary:
        incident.summary = summary
    incident.save(update_fields=['status','resolved_at','summary','updated_at'])
    add_timeline_event(incident, 'Incidente marcado como resolvido.', MPSMajorIncidentTimelineEvent.EventType.RESOLVED, actor)
    return incident


@transaction.atomic
def approve_postmortem(postmortem, actor):
    postmortem.status = MPSMajorIncidentPostmortem.Status.APPROVED
    postmortem.approved_by = actor
    postmortem.approved_at = timezone.now()
    postmortem.save(update_fields=['status','approved_by','approved_at','updated_at'])
    add_timeline_event(postmortem.incident, 'Postmortem aprovado.', MPSMajorIncidentTimelineEvent.EventType.DECISION, actor)
    return postmortem


@transaction.atomic
def close_major_incident(incident, actor=None):
    if incident.status != MPSMajorIncident.Status.RESOLVED:
        raise ValueError('Somente incidente RESOLVED pode ser encerrado.')
    policy = MPSIncidentCommandPolicy.objects.filter(plant=incident.plant, is_active=True).first()
    required = (policy.require_postmortem_for if policy else None) or ['SEV1','SEV2']
    if incident.severity in required:
        pm = MPSMajorIncidentPostmortem.objects.filter(incident=incident).first()
        if not pm or pm.status != MPSMajorIncidentPostmortem.Status.APPROVED:
            raise ValueError('A severidade exige postmortem APPROVED antes do fechamento.')
    open_actions = incident.actions.exclude(status__in=[MPSMajorIncidentAction.Status.DONE, MPSMajorIncidentAction.Status.CANCELLED]).count()
    if open_actions:
        raise ValueError(f'Existem {open_actions} ação(ões) de remediação ainda abertas.')
    incident.status = MPSMajorIncident.Status.CLOSED
    incident.closed_at = timezone.now()
    incident.closed_by = actor
    incident.save(update_fields=['status','closed_at','closed_by','updated_at'])
    add_timeline_event(incident, 'Incidente formalmente encerrado.', MPSMajorIncidentTimelineEvent.EventType.CLOSED, actor)
    return incident


def incident_command_metrics(plant=None, days=30):
    since = timezone.now() - timedelta(days=days)
    qs = MPSMajorIncident.objects.filter(started_at__gte=since)
    if plant:
        qs = qs.filter(plant=plant)
    rows = list(qs)
    resolve_minutes = [(x.resolved_at-x.started_at).total_seconds()/60 for x in rows if x.resolved_at]
    closed = [x for x in rows if x.status == MPSMajorIncident.Status.CLOSED]
    sev1 = sum(1 for x in rows if x.severity == MPSMajorIncident.Severity.SEV1)
    return {
        'major_incidents': len(rows),
        'active': sum(1 for x in rows if x.status in [MPSMajorIncident.Status.DETECTED,MPSMajorIncident.Status.ACTIVE,MPSMajorIncident.Status.MONITORING]),
        'closed': len(closed),
        'sev1': sev1,
        'mttr_minutes': round(sum(resolve_minutes)/len(resolve_minutes),2) if resolve_minutes else 0,
        'open_actions': MPSMajorIncidentAction.objects.filter(incident__in=qs).exclude(status__in=['DONE','CANCELLED']).count(),
    }


def incident_command_dashboard():
    from apps.common.models import Plant
    result=[]
    for plant in Plant.objects.order_by('code'):
        result.append({
            'plant':plant,
            'metrics':incident_command_metrics(plant),
            'incidents':MPSMajorIncident.objects.filter(plant=plant).select_related('commander').prefetch_related('compliance_incidents')[:50],
        })
    return result
