from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.common.models import ShopCalendarDay
from apps.demand.models import MasterProductionSchedule
from apps.masterdata.models import Routing, RoutingOperation, WorkCenter
from apps.planning.models import PlanningRun
from apps.planning.services import execute_planning_run
from .models import (
    SAndOPCycle, MPSOperationalPolicy, OperationalMPSPublication,
    MPSWeeklyBucket, MPSRCCPException,
)

ZERO=Decimal('0'); Q=Decimal('0.0001')
def q(v): return Decimal(v or 0).quantize(Q)

def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())

def iter_weeks(start: date, end: date):
    cur=week_start(start)
    while cur <= end:
        yield cur
        cur += timedelta(days=7)

def _overlap_weeks(month_bucket, horizon_start, horizon_end):
    if month_bucket.month == 12:
        month_end=date(month_bucket.year+1,1,1)-timedelta(days=1)
    else:
        month_end=date(month_bucket.year,month_bucket.month+1,1)-timedelta(days=1)
    s=max(month_bucket,horizon_start); e=min(month_end,horizon_end)
    return [max(w,s) for w in iter_weeks(s,e) if (w+timedelta(days=6))>=s and w<=e]

def _status_for_bucket(policy, as_of, bucket):
    d=(bucket-as_of).days
    if d <= policy.demand_time_fence_days:
        return 'FROZEN', f'Demand time fence até {as_of + timedelta(days=policy.demand_time_fence_days)}'
    if d <= policy.planning_time_fence_days:
        return 'FIRM', ''
    return 'PLANNED', ''

def _capacity_hours(wc: WorkCenter, bucket_start: date):
    total=ZERO
    calendar={r.date:r for r in ShopCalendarDay.objects.filter(plant=wc.plant,date__range=(bucket_start,bucket_start+timedelta(days=6)))}
    shifts=list(wc.shifts.filter(is_active=True))
    by_day=defaultdict(list)
    for s in shifts: by_day[s.weekday].append(s)
    for i in range(7):
        d=bucket_start+timedelta(days=i); cd=calendar.get(d)
        if cd and not cd.is_working_day: continue
        factor=Decimal(cd.capacity_factor if cd else 1)
        if by_day.get(d.weekday()):
            day=sum((Decimal(s.capacity_hours)*Decimal(s.efficiency_percent)/Decimal(100) for s in by_day[d.weekday()]),ZERO)
        elif d.weekday()<5:
            day=Decimal(wc.capacity_hours_per_day)*Decimal(wc.efficiency_percent)/Decimal(100)
        else:
            day=ZERO
        total += day*factor
    return q(total)

@transaction.atomic
def build_operational_mps(cycle: SAndOPCycle, user=None, as_of_date=None):
    if cycle.status not in [SAndOPCycle.Status.APPROVED, SAndOPCycle.Status.PUBLISHED]:
        raise ValueError('O MPS operacional exige ciclo S&OP aprovado ou publicado.')
    policy,_=MPSOperationalPolicy.objects.get_or_create(plant=cycle.plant)
    as_of_date=as_of_date or timezone.localdate()
    source=f'MPSOP:{cycle.plant.code}:{cycle.code}:v{cycle.version}:{as_of_date:%Y%m%d}'
    pub,created=OperationalMPSPublication.objects.get_or_create(
        source=source,
        defaults=dict(cycle=cycle,policy=policy,as_of_date=as_of_date,horizon_start=cycle.horizon_start,horizon_end=cycle.horizon_end,created_by=user),
    )
    if not created and pub.weekly_buckets.exists():
        raise ValueError('Este MPS operacional já foi construído. Use revisões 0.8.2 em vez de reconstruir destrutivamente o mesmo source.')
    pub.weekly_buckets.all().delete(); pub.rccp_exceptions.all().delete()
    rows=[]
    for line in cycle.supply_lines.select_related('item'):
        qty=q(line.capacity_constrained_quantity if line.capacity_constrained_quantity>0 else line.demand_quantity)
        if qty<=0: continue
        weeks=_overlap_weeks(line.bucket_date,cycle.horizon_start,cycle.horizon_end)
        if not weeks: continue
        base=(qty/len(weeks)).quantize(Q); allocated=ZERO
        for idx,w in enumerate(weeks):
            piece=q(qty-allocated) if idx==len(weeks)-1 else base
            allocated+=piece
            st,reason=_status_for_bucket(policy,as_of_date,w)
            rows.append(MPSWeeklyBucket(publication=pub,item=line.item,bucket_start=w,bucket_end=min(w+timedelta(days=6),cycle.horizon_end),quantity=piece,baseline_quantity=piece,
                source_demand_quantity=q(line.demand_quantity/len(weeks)),source_supply_quantity=q(line.planned_supply_quantity/len(weeks)),mps_status=st,frozen_reason=reason))
    MPSWeeklyBucket.objects.bulk_create(rows)
    pub.summary={'weekly_buckets':len(rows),'quantity':str(q(sum((r.quantity for r in rows),ZERO))),'frozen':sum(1 for r in rows if r.mps_status=='FROZEN'),'firm':sum(1 for r in rows if r.mps_status=='FIRM'),'planned':sum(1 for r in rows if r.mps_status=='PLANNED')}
    pub.status=OperationalMPSPublication.Status.DRAFT; pub.save(update_fields=['summary','status','updated_at'])
    run_rccp(pub)
    if not pub.revisions.exists():
        from .mps_revision import capture_revision
        capture_revision(pub,user,kind='BASELINE',label='Baseline S&OP → MPS',auto_approve=True)
    return pub

@transaction.atomic
def run_rccp(pub: OperationalMPSPublication):
    pub.rccp_exceptions.all().delete()
    required=defaultdict(Decimal)
    for b in pub.weekly_buckets.select_related('item'):
        routing=Routing.objects.filter(plant=pub.cycle.plant,item=b.item,is_active=True,is_primary=True).order_by('-version').first()
        if not routing: continue
        for op in routing.operations.select_related('work_center'):
            hours=Decimal(op.setup_hours)+Decimal(op.teardown_hours)+(Decimal(op.run_hours_per_unit)*Decimal(b.quantity))
            required[(op.work_center_id,b.bucket_start)] += hours
    exceptions=[]; overloads=ZERO
    for (wc_id,w), req in required.items():
        wc=WorkCenter.objects.get(pk=wc_id); cap=_capacity_hours(wc,w); over=max(q(req)-cap,ZERO)
        pct=q((over/cap*100) if cap>0 else (Decimal(100) if over>0 else ZERO))
        tol=Decimal(pub.policy.overload_tolerance_percent)
        if over>0:
            sev=MPSRCCPException.Severity.CRITICAL if pct>max(Decimal(10),tol) else MPSRCCPException.Severity.WARNING
            exceptions.append(MPSRCCPException(publication=pub,work_center=wc,bucket_start=w,required_hours=q(req),available_hours=cap,overload_hours=over,overload_percent=pct,severity=sev,message=f'{wc.code}: carga {q(req)}h > capacidade {cap}h ({pct}% excesso).'))
            overloads+=over
    MPSRCCPException.objects.bulk_create(exceptions)
    blocking=MPSRCCPException.objects.filter(publication=pub,status=MPSRCCPException.Status.OPEN,severity=MPSRCCPException.Severity.CRITICAL).count()
    pub.validation_summary={'rccp_exceptions':len(exceptions),'critical_open':blocking,'overload_hours':str(q(overloads))}
    pub.status=OperationalMPSPublication.Status.BLOCKED if (pub.policy.require_rccp_clear and blocking) else OperationalMPSPublication.Status.VALIDATED
    pub.save(update_fields=['validation_summary','status','updated_at'])
    return pub

@transaction.atomic
def publish_operational_mps(pub: OperationalMPSPublication, user=None, force=False):
    from .mps_revision import latest_revision
    rev=latest_revision(pub)
    if rev and rev.status!='APPROVED' and not force:
        raise ValueError(f'Revisão r{rev.number} precisa ser aprovada antes da publicação.')
    if pub.status==OperationalMPSPublication.Status.BLOCKED and not force:
        raise ValueError('Publicação bloqueada por exceções RCCP críticas abertas.')
    if pub.status not in [OperationalMPSPublication.Status.VALIDATED,OperationalMPSPublication.Status.BLOCKED]:
        raise ValueError('MPS operacional precisa estar validado antes da publicação.')
    MasterProductionSchedule.objects.filter(plant=pub.cycle.plant,source=pub.source).delete()
    count=0
    for b in pub.weekly_buckets.select_related('item'):
        if b.quantity<=0: continue
        status={'FROZEN':MasterProductionSchedule.Status.FROZEN,'FIRM':MasterProductionSchedule.Status.FIRM,'PLANNED':MasterProductionSchedule.Status.PLANNED}[b.mps_status]
        m=MasterProductionSchedule.objects.create(plant=pub.cycle.plant,item=b.item,due_date=b.bucket_start,quantity=b.quantity,status=status,source=pub.source,notes=f'{pub.cycle.code} v{pub.cycle.version}; bucket semanal {b.bucket_start}.')
        b.published_mps=m; b.save(update_fields=['published_mps','updated_at']); count+=1
    run=None
    if pub.policy.auto_create_planning_run:
        run=PlanningRun.objects.create(name=f'MRP from {pub.source}',plant=pub.cycle.plant,horizon_start=pub.horizon_start,horizon_end=pub.horizon_end,parameters={'source':'OPERATIONAL_MPS','operational_mps_publication_id':pub.id,'mps_source':pub.source,'include_sales_orders':False,'include_forecasts':False})
    pub.planning_run=run; pub.status=OperationalMPSPublication.Status.PUBLISHED; pub.published_by=user; pub.published_at=timezone.now();
    pub.summary={**pub.summary,'published_mps_lines':count,'planning_run_id':run.id if run else None}
    pub.save(update_fields=['planning_run','status','published_by','published_at','summary','updated_at'])
    return pub

@transaction.atomic
def execute_publication_mrp(pub: OperationalMPSPublication):
    if pub.status!=OperationalMPSPublication.Status.PUBLISHED or not pub.planning_run_id:
        raise ValueError('A publicação precisa estar PUBLISHED e possuir PlanningRun.')
    pub.status=OperationalMPSPublication.Status.MRP_RUNNING; pub.mrp_started_at=timezone.now(); pub.save(update_fields=['status','mrp_started_at','updated_at'])
    try:
        run=execute_planning_run(pub.planning_run)
        pub.status=OperationalMPSPublication.Status.MRP_COMPLETED if run.status==PlanningRun.Status.COMPLETED else OperationalMPSPublication.Status.FAILED
        pub.mrp_completed_at=timezone.now(); pub.error_message=run.error_message
        pub.save(update_fields=['status','mrp_completed_at','error_message','updated_at'])
        return run
    except Exception as exc:
        pub.status=OperationalMPSPublication.Status.FAILED; pub.error_message=str(exc); pub.mrp_completed_at=timezone.now(); pub.save(update_fields=['status','error_message','mrp_completed_at','updated_at']); raise
