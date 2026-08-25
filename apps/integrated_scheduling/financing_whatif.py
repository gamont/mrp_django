from __future__ import annotations
from decimal import Decimal
from django.db import transaction
from django.db.models import Q

from .models import FinancingPolicy, FinancingFacility, MPSRevisionSimulationFinancingBucket
from .mps_cashflow_whatif import money

D=Decimal

def _active_facilities(plant, start, end):
    return list(FinancingFacility.objects.filter(plant=plant,is_active=True).filter(Q(effective_from__isnull=True)|Q(effective_from__lte=end)).filter(Q(effective_to__isnull=True)|Q(effective_to__gte=start)).order_by('priority','code'))

def _period_days(current_date, next_date):
    if not next_date: return 30
    return max(1,(next_date-current_date).days)

def _weighted_rate(facilities):
    total=sum((D(f.limit_amount) for f in facilities),D('0'))
    if total<=0:return D('0')
    return sum((D(f.limit_amount)*D(f.annual_interest_rate_percent) for f in facilities),D('0'))/total

@transaction.atomic
def build_financing_impact(simulation):
    sim=simulation
    wc=list(sim.working_capital_buckets.order_by('bucket_date'))
    if not wc:
        from .working_capital_whatif import build_working_capital_impact
        build_working_capital_impact(sim); wc=list(sim.working_capital_buckets.order_by('bucket_date'))
    if not wc:return {'status':'UNAVAILABLE','warning':'Sem projeção de capital de giro para financiar.'}
    plant=sim.revision.publication.cycle.plant
    policy,_=FinancingPolicy.objects.get_or_create(plant=plant)
    facilities=_active_facilities(plant,wc[0].bucket_date,wc[-1].bucket_date)
    gross_limit=sum((D(f.limit_amount) for f in facilities),D('0'))
    usable_limit=gross_limit*D(policy.max_financing_utilization_percent)/D('100')
    rate=_weighted_rate(facilities)
    sim.financing_buckets.all().delete(); rows=[]
    lint=rint=D('0'); peak_l=peak_r=D('0'); peak_ul=peak_ur=D('0'); peak_date_l=peak_date_r=None
    for i,row in enumerate(wc):
        days=_period_days(row.bucket_date,wc[i+1].bucket_date if i+1<len(wc) else None)
        lreq=max(D('0'),D(row.left_working_capital_need)); rreq=max(D('0'),D(row.right_working_capital_need))
        ldraw=min(lreq,usable_limit); rdraw=min(rreq,usable_limit)
        lun=max(D('0'),lreq-usable_limit); run=max(D('0'),rreq-usable_limit)
        li=ldraw*rate/D('100')*D(days)/D('365'); ri=rdraw*rate/D('100')*D(days)/D('365')
        lint+=li; rint+=ri
        if ldraw>peak_l: peak_l=ldraw; peak_date_l=row.bucket_date
        if rdraw>peak_r: peak_r=rdraw; peak_date_r=row.bucket_date
        peak_ul=max(peak_ul,lun); peak_ur=max(peak_ur,run)
        rows.append(MPSRevisionSimulationFinancingBucket(simulation=sim,bucket_date=row.bucket_date,left_required_financing=money(lreq),right_required_financing=money(rreq),left_financing_outstanding=money(ldraw),right_financing_outstanding=money(rdraw),left_available_credit=money(max(D('0'),usable_limit-ldraw)),right_available_credit=money(max(D('0'),usable_limit-rdraw)),left_uncovered_need=money(lun),right_uncovered_need=money(run),left_interest_expense=money(li),right_interest_expense=money(ri),details={'period_days':days,'weighted_annual_rate_percent':str(rate),'gross_limit':str(money(gross_limit)),'usable_limit':str(money(usable_limit))}))
    MPSRevisionSimulationFinancingBucket.objects.bulk_create(rows)
    feasible_left=peak_ul<=0; feasible_right=peak_ur<=0
    out={'status':'COMPLETE','facility_count':len(facilities),'gross_credit_limit':str(money(gross_limit)),'usable_credit_limit':str(money(usable_limit)),'max_utilization_percent':str(policy.max_financing_utilization_percent),'weighted_annual_interest_rate_percent':str(rate),'peak_draw':{'left':str(money(peak_l)),'right':str(money(peak_r)),'delta':str(money(peak_r-peak_l)),'left_date':str(peak_date_l) if peak_date_l else None,'right_date':str(peak_date_r) if peak_date_r else None},'interest_cost':{'left':str(money(lint)),'right':str(money(rint)),'delta':str(money(rint-lint))},'peak_uncovered_need':{'left':str(money(peak_ul)),'right':str(money(peak_ur))},'financially_feasible':{'left':feasible_left,'right':feasible_right},'approval_block_enabled':policy.block_revision_approval_when_exceeded,'warning':'Financiamento 0.8.7 é uma simulação gerencial. Juros usam taxa anual ponderada e saldo de necessidade por bucket; não substitui contratos bancários, tesouraria, IOF, tarifas, covenants ou calendário bancário real.'}
    fs=dict(sim.financial_summary or {}); fs['financing_087']=out; sim.financial_summary=fs; sim.save(update_fields=['financial_summary','updated_at'])
    return out
