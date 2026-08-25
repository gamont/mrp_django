from collections import Counter
from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.demand.models import SalesOrderLine, SalesDeliveryLine
from .models import (SalesOrderPromise, CustomerPromiseResponse, OTIFLineResult, ServiceLevelCause,
                     RecoveryCommercialImpact, ScheduleExecutionDeviation)

def _approved_date(line):
    p=(SalesOrderPromise.objects.filter(sales_order_line=line,status=SalesOrderPromise.Status.APPROVED).order_by('-decided_at','-created_at').first())
    return p.proposed_date if p else None

def _accepted_date(line):
    r=(CustomerPromiseResponse.objects.filter(promise__sales_order_line=line,response=CustomerPromiseResponse.Response.ACCEPTED,confirmed_date__isnull=False).order_by('-received_at').first())
    return r.confirmed_date if r else None

def service_reference_date(line, reference='CUSTOMER_ACCEPTED'):
    approved=_approved_date(line); accepted=_accepted_date(line)
    if reference=='REQUESTED': ref=line.requested_date
    elif reference=='APPROVED_PROMISE': ref=approved or line.requested_date
    else: ref=accepted or approved or line.requested_date
    return ref, approved, accepted

def _delivery_facts(line):
    qs=SalesDeliveryLine.objects.filter(sales_order_line=line).select_related('delivery').order_by('delivery__delivery_date','id')
    delivered=Decimal('0'); first=None; full=None
    for row in qs:
        delivered += row.quantity
        first = first or row.delivery.delivery_date
        if full is None and delivered >= line.quantity:
            full=row.delivery.delivery_date
    return min(delivered, line.quantity), first, full

def _infer_primary_cause(line, result):
    # Uses explicit operational evidence when available; otherwise UNKNOWN.
    rec=(RecoveryCommercialImpact.objects.filter(sales_order_line=line).order_by('-created_at').first())
    if rec and rec.trigger_id:
        t=rec.trigger.trigger_type
        mapping={'MACHINE_BREAKDOWN':'MACHINE','MATERIAL_SHORTAGE':'MATERIAL','LABOR_ABSENCE':'LABOR','PRIORITY_CHANGE':'COMMERCIAL'}
        return mapping.get(t,'UNKNOWN'), {'trigger_id':rec.trigger_id,'trigger_type':t}
    dev=(ScheduleExecutionDeviation.objects.filter(slot__operation__work_order__item=line.item).order_by('-created_at').first())
    if dev:
        mapping={'MACHINE_BREAKDOWN':'MACHINE','MATERIAL_SHORTAGE':'MATERIAL','LABOR_ABSENCE':'LABOR'}
        return mapping.get(dev.deviation_type,'CAPACITY'), {'deviation_id':dev.id,'deviation_type':dev.deviation_type}
    return 'UNKNOWN', {}

@transaction.atomic
def evaluate_otif_line(line, reference='CUSTOMER_ACCEPTED'):
    ref, approved, accepted=service_reference_date(line, reference)
    delivered, first, full=_delivery_facts(line)
    in_full=delivered >= line.quantity
    on_time=bool(full and full <= ref)
    days_late=max((full-ref).days,0) if full else max((timezone.localdate()-ref).days,0)
    cause,details=_infer_primary_cause(line, None) if (not on_time or not in_full) else ('','')
    obj,_=OTIFLineResult.objects.update_or_create(
        sales_order_line=line, reference=reference,
        defaults=dict(requested_date=line.requested_date,approved_promise_date=approved,accepted_date=accepted,reference_date=ref,
                      ordered_quantity=line.quantity,delivered_quantity=delivered,first_delivery_date=first,full_delivery_date=full,
                      on_time=on_time,in_full=in_full,otif=on_time and in_full,days_late=days_late,primary_cause=cause,
                      cause_details=details or {},evaluated_at=timezone.now()))
    obj.causes.all().delete()
    if cause:
        ServiceLevelCause.objects.create(otif_result=obj,category=cause,description=f'Causa primária inferida: {cause}',is_primary=True,details=details or {})
    return obj

def evaluate_otif_queryset(qs, reference='CUSTOMER_ACCEPTED'):
    return [evaluate_otif_line(line, reference) for line in qs.select_related('sales_order','item')]

def service_level_summary(qs):
    rows=list(qs)
    n=len(rows)
    def pct(v): return round((v*100/n),2) if n else 0
    on=sum(1 for r in rows if r.on_time); inf=sum(1 for r in rows if r.in_full); ot=sum(1 for r in rows if r.otif)
    causes=Counter(r.primary_cause or 'UNKNOWN' for r in rows if not r.otif)
    return {'lines':n,'on_time_pct':pct(on),'in_full_pct':pct(inf),'otif_pct':pct(ot),
            'late_lines':sum(1 for r in rows if not r.on_time),'incomplete_lines':sum(1 for r in rows if not r.in_full),
            'causes':[{'category':k,'count':v} for k,v in causes.most_common()]}
