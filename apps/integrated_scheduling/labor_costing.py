from __future__ import annotations
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q
from django.utils import timezone
from .models import LaborRuleSet, ScheduleSolverLaborAssignment, ScheduleSolverLaborCost

D=Decimal

def active_rule_set(plant, on_date):
    return (LaborRuleSet.objects.filter(plant=plant, is_active=True, effective_from__lte=on_date)
            .filter(Q(effective_to__isnull=True)|Q(effective_to__gte=on_date)).order_by('-effective_from').first())

def _overlap_minutes(a,b,c,d):
    return max(0, int((min(b,d)-max(a,c)).total_seconds()//60)) if min(b,d)>max(a,c) else 0

def night_minutes(start, end, rule):
    if not rule: return 0
    total=0; day=start.date()-timedelta(days=1)
    while day<=end.date():
        ns=datetime.combine(day, rule.night_start); ne_day=day+timedelta(days=1) if rule.night_end<=rule.night_start else day
        ne=datetime.combine(ne_day, rule.night_end)
        if timezone.is_aware(start): ns=timezone.make_aware(ns); ne=timezone.make_aware(ne)
        total += _overlap_minutes(start,end,ns,ne); day += timedelta(days=1)
    return total

def calculate_run_labor_costs(run):
    ScheduleSolverLaborCost.objects.filter(labor_assignment__run=run).delete()
    assignments=list(ScheduleSolverLaborAssignment.objects.filter(run=run).select_related('labor_resource','operation__work_order__plant').order_by('labor_resource_id','start','pk'))
    daily_used=defaultdict(int); total=D('0')
    for a in assignments:
        rule=run.labor_rule_set or active_rule_set(run.scenario.plant, a.start.date())
        mins=max(0,int((a.end-a.start).total_seconds()//60)); key=(a.labor_resource_id,a.start.date())
        normal_limit=int(D(str(rule.normal_daily_hours if rule else 8))*60)
        normal=max(0,min(mins, normal_limit-daily_used[key])); overtime=max(0,mins-normal); daily_used[key]+=mins
        night=night_minutes(a.start,a.end,rule)
        rate=D(str(a.labor_resource.hourly_cost or 0)); base=(rate*D(mins)/D(60))
        ot_mult=D(str(rule.overtime_multiplier if rule else '1.5'))
        ot_premium=rate*D(overtime)/D(60)*(ot_mult-D(1))
        night_pct=D(str(rule.night_premium_percent if rule else 0))/D(100)
        night_premium=rate*D(night)/D(60)*night_pct
        row_total=base+ot_premium+night_premium
        q=lambda x:x.quantize(D('0.0001'), rounding=ROUND_HALF_UP)
        ScheduleSolverLaborCost.objects.create(labor_assignment=a, normal_minutes=normal, overtime_minutes=overtime, night_minutes=night,
            base_cost=q(base), overtime_premium=q(ot_premium), night_premium=q(night_premium), total_cost=q(row_total), rule_set=rule,
            details={'hourly_cost':str(rate),'overtime_multiplier':str(ot_mult),'night_premium_percent':str(rule.night_premium_percent if rule else 0)})
        total += row_total
    run.labor_cost_total=total.quantize(D('0.0001'),rounding=ROUND_HALF_UP); run.save(update_fields=['labor_cost_total','updated_at']); return run.labor_cost_total
