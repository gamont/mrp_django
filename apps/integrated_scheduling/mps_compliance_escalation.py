from __future__ import annotations
from datetime import timedelta
import json
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Count
from django.utils import timezone

from .models import (
    MPSDecisionComplianceIncident, MPSComplianceEscalationPolicy,
    MPSComplianceEscalationRule, MPSComplianceOnCallContact,
    MPSComplianceEscalationEvent, MPSComplianceHoliday,
    MPSComplianceOnCallAbsence, MPSComplianceOnCallSubstitution,
    MPSComplianceNotificationDelivery,
)


def get_escalation_policy(plant):
    policy, _ = MPSComplianceEscalationPolicy.objects.get_or_create(plant=plant)
    return policy


def _rule_matches(rule, incident):
    return ((not rule.severities or incident.severity in rule.severities) and
            (not rule.categories or incident.category in rule.categories))


def _plant_local(now, plant):
    try:
        return now.astimezone(ZoneInfo(plant.timezone))
    except Exception:
        return timezone.localtime(now)


def _is_holiday(plant, now):
    local = _plant_local(now, plant)
    return MPSComplianceHoliday.objects.filter(plant=plant, date=local.date(), is_active=True).exists()


def _is_absent(contact, now):
    return MPSComplianceOnCallAbsence.objects.filter(contact=contact, is_active=True, starts_at__lte=now, ends_at__gte=now).exists()


def _on_call_now(contact, now):
    if not contact.is_active or _is_absent(contact, now):
        return False
    local = _plant_local(now, contact.plant)
    if _is_holiday(contact.plant, now) and not contact.include_holidays:
        return False
    if contact.weekdays and local.weekday() not in contact.weekdays:
        return False
    if contact.start_time is None or contact.end_time is None:
        return True
    t = local.time().replace(tzinfo=None)
    if contact.start_time <= contact.end_time:
        return contact.start_time <= t <= contact.end_time
    return t >= contact.start_time or t <= contact.end_time


def _substitute_for(contact, level, now):
    qs = MPSComplianceOnCallSubstitution.objects.select_related('substitute_contact').filter(
        primary_contact=contact, is_active=True, starts_at__lte=now, ends_at__gte=now).order_by('-starts_at')
    for sub in qs:
        if sub.levels and level not in sub.levels:
            continue
        if _on_call_now(sub.substitute_contact, now):
            return sub.substitute_contact
    return None


def _active_contacts(rule, policy, now):
    if not policy.use_on_call_contacts:
        return []
    result=[]; seen=set()
    for contact in MPSComplianceOnCallContact.objects.filter(plant=policy.plant, is_active=True):
        if contact.levels and rule.level not in contact.levels:
            continue
        chosen = contact if _on_call_now(contact, now) else _substitute_for(contact, rule.level, now)
        if chosen and chosen.id not in seen:
            seen.add(chosen.id); result.append(chosen)
    return result


def _recipient_emails(rule, policy, contacts):
    emails = {e.strip() for e in (rule.recipient_emails or []) if e and e.strip()}
    if rule.recipient_groups:
        User = get_user_model()
        for email in User.objects.filter(is_active=True, groups__name__in=rule.recipient_groups).exclude(email='').values_list('email', flat=True).distinct():
            emails.add(email)
    for c in contacts:
        if c.email:
            emails.add(c.email)
    return sorted(emails)


def _notification_limits(rule, policy):
    return rule.repeat_interval_minutes or policy.repeat_interval_minutes, rule.max_notifications or policy.max_repeat_notifications


def _should_notify(event, rule, policy, now):
    interval, maximum = _notification_limits(rule, policy)
    if event.notification_count == 0: return True
    if not policy.repeat_notifications or event.notification_count >= maximum: return False
    return bool(event.last_notified_at and now - event.last_notified_at >= timedelta(minutes=interval))


def _clock_start(rule, incident):
    if rule.clock_basis == MPSComplianceEscalationRule.ClockBasis.ACKNOWLEDGED:
        return incident.acknowledged_at
    return incident.first_seen_at


def _payload(event, incident, now):
    elapsed = round((now - incident.first_seen_at).total_seconds()/60, 1)
    return {
        'cockpit_id': incident.cockpit_id, 'incident_id': incident.id,
        'category': incident.category, 'severity': incident.severity,
        'status': incident.status, 'escalation_level': event.level,
        'elapsed_minutes': elapsed, 'message': incident.message,
        'responsible_area': incident.responsible_area,
        'responsible_user': incident.responsible_user.get_username() if incident.responsible_user_id else '',
    }


def _delivery(event, channel, destination, status, code=None, error='', details=None):
    return MPSComplianceNotificationDelivery.objects.create(event=event, channel=channel, destination=destination or '', status=status, response_code=code, error=error, details=details or {})


def _post_json(url, payload):
    body=json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req=urlrequest.Request(url, data=body, headers={'Content-Type':'application/json','User-Agent':'MRP-Compliance/0.9.8'}, method='POST')
    with urlrequest.urlopen(req, timeout=10) as resp:
        return int(resp.status)


def _send_channels(event, rule, policy, contacts, now):
    incident=event.incident; payload=_payload(event, incident, now)
    channels=[str(c).upper() for c in (rule.notification_channels or ['EMAIL'])]
    sent=[]
    for channel in channels:
        if channel == 'EMAIL':
            recipients=_recipient_emails(rule, policy, contacts) if policy.send_email else []
            subject=f'[MRP] Escalation {event.level} · {incident.severity} · incident #{incident.id}'
            body='\n'.join([f'Cockpit: #{incident.cockpit_id}',f'Incidente: #{incident.id} · {incident.category}',f'Severidade: {incident.severity}',f'Escalonamento: {event.level}',f'Tempo aberto: {payload["elapsed_minutes"]} min','',incident.message])
            try:
                if recipients: send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
                _delivery(event,'EMAIL',','.join(recipients),'SENT' if recipients else 'SKIPPED',details={'recipients':recipients})
                sent.append({'channel':'EMAIL','destinations':recipients})
            except Exception as exc:
                _delivery(event,'EMAIL',','.join(recipients),'FAILED',error=str(exc))
        else:
            endpoints=[]
            if (rule.channel_endpoints or {}).get(channel): endpoints.append((rule.channel_endpoints or {})[channel])
            for c in contacts:
                u={'API':c.api_url,'TEAMS':c.teams_webhook_url,'SLACK':c.slack_webhook_url}.get(channel,'')
                if u: endpoints.append(u)
            for endpoint in sorted(set(endpoints)):
                try:
                    wire={'text': f'[MRP] {event.level} {incident.severity} incident #{incident.id}: {incident.message}', 'mrp':payload}
                    code=_post_json(endpoint, wire)
                    _delivery(event,channel,endpoint,'SENT',code=code); sent.append({'channel':channel,'destination':endpoint,'code':code})
                except (HTTPError,URLError,TimeoutError,OSError,ValueError) as exc:
                    code=getattr(exc,'code',None); _delivery(event,channel,endpoint,'FAILED',code=code,error=str(exc))
    event.notification_count += 1
    event.first_notified_at = event.first_notified_at or now
    event.last_notified_at = now
    event.recipients = _recipient_emails(rule,policy,contacts)
    event.details = {**(event.details or {}),'last_elapsed_minutes':payload['elapsed_minutes'],'last_channels':channels}
    event.save(update_fields=['notification_count','first_notified_at','last_notified_at','recipients','details','updated_at'])
    return sent


def evaluate_incident_escalation(incident, now=None, send_notifications=True):
    now=now or timezone.now(); plant=incident.cockpit.publication.policy.plant; policy=get_escalation_policy(plant)
    if not policy.is_active: return {'incident_id':incident.id,'skipped':True,'reason':'policy_inactive'}
    if incident.status == MPSDecisionComplianceIncident.Status.RESOLVED:
        incident.escalation_events.filter(status=MPSComplianceEscalationEvent.Status.ACTIVE).update(status=MPSComplianceEscalationEvent.Status.STOPPED,stopped_at=now,updated_at=now)
        return {'incident_id':incident.id,'resolved':True,'active_levels':[]}
    active=[]; notified=[]
    for rule in policy.rules.filter(is_active=True).order_by('after_minutes','order','id'):
        if not _rule_matches(rule, incident): continue
        start=_clock_start(rule,incident)
        if start is None: continue  # ACK clock waits for acknowledgement
        elapsed=(now-start).total_seconds()/60
        if elapsed < rule.after_minutes: continue
        event,_=MPSComplianceEscalationEvent.objects.get_or_create(incident=incident,rule=rule,defaults={'level':rule.level,'activated_at':now,'details':{'threshold_minutes':rule.after_minutes,'clock_basis':rule.clock_basis}})
        active.append(rule.level)
        try:
            from .mps_incident_command import maybe_auto_promote
            maybe_auto_promote(incident, rule.level)
        except Exception:
            # Incident command must not prevent the escalation engine from continuing.
            pass
        if send_notifications and _should_notify(event,rule,policy,now):
            contacts=_active_contacts(rule,policy,now); deliveries=_send_channels(event,rule,policy,contacts,now)
            notified.append({'event_id':event.id,'level':rule.level,'deliveries':deliveries})
    return {'incident_id':incident.id,'active_levels':active,'notifications':notified}


def run_escalation_engine(plant=None, send_notifications=True):
    qs=MPSDecisionComplianceIncident.objects.select_related('cockpit__publication__policy__plant','responsible_user').filter(status__in=[MPSDecisionComplianceIncident.Status.OPEN,MPSDecisionComplianceIncident.Status.ACKNOWLEDGED])
    if plant is not None: qs=qs.filter(cockpit__publication__policy__plant=plant)
    return [evaluate_incident_escalation(i,send_notifications=send_notifications) for i in qs]


def escalation_metrics(plant, days=30):
    since=timezone.now()-timedelta(days=days)
    qs=MPSDecisionComplianceIncident.objects.filter(cockpit__publication__policy__plant=plant,first_seen_at__gte=since)
    ack=[]; resolve=[]; breaches=0
    for i in qs:
        if i.acknowledged_at: ack.append((i.acknowledged_at-i.first_seen_at).total_seconds()/60)
        if i.resolved_at: resolve.append((i.resolved_at-i.first_seen_at).total_seconds()/60)
        # Any manager-or-higher escalation is considered an SLA escalation/breach proxy.
        if i.escalation_events.filter(level__in=['MANAGER','DIRECTOR','EXECUTIVE']).exists(): breaches+=1
    avg=lambda x: round(sum(x)/len(x),2) if x else 0
    def grouped(field):
        buckets={}
        for inc in qs.select_related('responsible_user'):
            if field == 'area': key=inc.responsible_area or 'UNASSIGNED'
            else: key=inc.responsible_user.get_username() if inc.responsible_user_id else 'UNASSIGNED'
            row=buckets.setdefault(key, {'key':key,'incidents':0,'sla_breaches':0})
            row['incidents'] += 1
            if inc.escalation_events.filter(level__in=['MANAGER','DIRECTOR','EXECUTIVE']).exists(): row['sla_breaches'] += 1
        return sorted(buckets.values(), key=lambda x:(-x['sla_breaches'],-x['incidents'],x['key']))
    by_area=grouped('area'); by_responsible=grouped('responsible')
    return {'window_days':days,'incident_count':qs.count(),'mtta_minutes':avg(ack),'mttr_minutes':avg(resolve),'ack_sample_count':len(ack),'resolve_sample_count':len(resolve),'sla_escalated_incidents':breaches,'active_escalations':MPSComplianceEscalationEvent.objects.filter(incident__cockpit__publication__policy__plant=plant,status='ACTIVE').count(),'by_area':by_area,'by_responsible':by_responsible}


def escalation_dashboard():
    rows=[]
    for policy in MPSComplianceEscalationPolicy.objects.select_related('plant').filter(is_active=True):
        events=MPSComplianceEscalationEvent.objects.select_related('incident__cockpit','rule').filter(incident__cockpit__publication__policy__plant=policy.plant,status='ACTIVE').order_by('-activated_at')
        holidays=MPSComplianceHoliday.objects.filter(plant=policy.plant,is_active=True,date__gte=timezone.localdate()).order_by('date')[:10]
        rows.append({'plant':policy.plant,'policy':policy,'metrics':escalation_metrics(policy.plant),'events':list(events[:100]),'holidays':list(holidays)})
    return rows
