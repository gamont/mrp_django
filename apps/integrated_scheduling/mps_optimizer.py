from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.masterdata.models import ItemSupplier
from apps.planning.models import PlannedOrder
from .models import (
    MPSOptimizationPolicy, MPSRevisionOptimizationRun,
    MPSRevisionOptimizationCandidate, MPSRevisionOptimizationAction,
    MPSRevision, MPSRevisionLine, MPSWeeklyBucket,
)
from .mps_whatif import create_simulation, run_simulation

D=Decimal; Q=D('0.0001')
def q(v): return D(v or 0).quantize(Q)
def num(v):
    try:return D(str(v or 0))
    except Exception:return D('0')


def create_optimization_run(revision, compare_revision=None, user=None):
    if compare_revision is None:
        compare_revision=revision.publication.revisions.filter(kind=MPSRevision.Kind.BASELINE).order_by('number').first() or revision.parent
    if not compare_revision: raise ValueError('Não existe revisão baseline para comparar.')
    if compare_revision.publication_id!=revision.publication_id: raise ValueError('As revisões pertencem a MPS diferentes.')
    return MPSRevisionOptimizationRun.objects.create(revision=revision,compare_revision=compare_revision,created_by=user)


def _snapshot_lines(revision):
    return [{
        'item_id':x.item_id,'bucket_start':x.bucket_start,'bucket_end':x.bucket_end,
        'quantity':q(x.quantity),'baseline_quantity':q(x.baseline_quantity),
        'mps_status':x.mps_status,'frozen_reason':x.frozen_reason,
    } for x in revision.lines.all()]


def _overrides_from_lines(lines):
    return {
        'inline_mps_demands':[{'item_id':x['item_id'],'due_date':x['bucket_start'].isoformat(),'quantity':str(q(x['quantity'])),'source_model':'MPSOptimizationCandidate'} for x in lines if x['quantity']>0],
        'candidate_mps_lines':[{**x,'bucket_start':x['bucket_start'].isoformat(),'bucket_end':x['bucket_end'].isoformat(),'quantity':str(q(x['quantity'])),'baseline_quantity':str(q(x['baseline_quantity']))} for x in lines],
    }


def _shift_candidate(run,strategy,direction,fraction):
    lines=_snapshot_lines(run.revision); by={(x['item_id'],x['bucket_start']):x for x in lines}
    cand=MPSRevisionOptimizationCandidate.objects.create(optimization_run=run,strategy=strategy,name=f'{strategy}: redistribuição {fraction}%')
    eligible=sorted([x for x in lines if x['quantity']>0 and x['mps_status']!='FROZEN'],key=lambda x:(-x['quantity'],x['bucket_start'],x['item_id']))
    moved=0
    for line in eligible:
        target=by.get((line['item_id'],line['bucket_start']+timedelta(days=7*direction)))
        if not target or target['mps_status']=='FROZEN':continue
        amount=q(line['quantity']*D(fraction)/D('100'))
        if amount<=0 or amount>line['quantity']:continue
        line['quantity']=q(line['quantity']-amount); target['quantity']=q(target['quantity']+amount)
        MPSRevisionOptimizationAction.objects.create(candidate=cand,action_type='MOVE_VOLUME',item_id=line['item_id'],source_date=line['bucket_start'],target_date=target['bucket_start'],quantity=amount,details={'strategy':strategy})
        moved+=1
        if moved>=3:break
    cand.planning_overrides=_overrides_from_lines(lines); cand.notes='' if moved else 'Nenhum movimento elegível fora da zona congelada.'; cand.save(update_fields=['planning_overrides','notes','updated_at'])
    return cand


def _level_candidate(run,fraction):
    lines=_snapshot_lines(run.revision); groups=defaultdict(list)
    for x in lines:groups[x['item_id']].append(x)
    cand=MPSRevisionOptimizationCandidate.objects.create(optimization_run=run,strategy=MPSRevisionOptimizationCandidate.Strategy.LEVEL_LOAD,name='Nivelamento simples entre semanas')
    actions=0
    for item_id,rows in groups.items():
        movable=[x for x in rows if x['mps_status']!='FROZEN']
        if len(movable)<2:continue
        high=max(movable,key=lambda x:x['quantity']); low=min(movable,key=lambda x:x['quantity'])
        if high is low or high['quantity']<=low['quantity']:continue
        amount=q((high['quantity']-low['quantity'])*D(fraction)/D('200'))
        if amount<=0:continue
        high['quantity']=q(high['quantity']-amount); low['quantity']=q(low['quantity']+amount)
        MPSRevisionOptimizationAction.objects.create(candidate=cand,action_type='LEVEL_VOLUME',item_id=item_id,source_date=high['bucket_start'],target_date=low['bucket_start'],quantity=amount)
        actions+=1
        if actions>=4:break
    cand.planning_overrides=_overrides_from_lines(lines); cand.save(update_fields=['planning_overrides','updated_at']); return cand


def _supplier_override_candidate(run,base_sim,policy):
    if not policy.allow_supplier_switch:return None
    plant=run.revision.publication.cycle.plant
    ids=set(base_sim.target_planning_run.planned_orders.filter(order_type=PlannedOrder.OrderType.PURCHASE).values_list('item_id',flat=True))
    rows=ItemSupplier.objects.select_related('supplier').filter(plant=plant,item_id__in=ids,supplier__is_active=True).order_by('item_id','supplier__payment_terms_days')
    by=defaultdict(list)
    for x in rows:by[x.item_id].append(x)
    overrides={}; selected=[]
    for item_id,options in by.items():
        primary=next((x for x in options if x.is_primary),None)
        if not primary:continue
        pprice=D(primary.unit_price or 0); maxprice=pprice*(D('1')+D(policy.supplier_price_tolerance_percent)/D('100')) if pprice>0 else None
        alts=[x for x in options if x.id!=primary.id and x.supplier.payment_terms_days>primary.supplier.payment_terms_days and (maxprice is None or D(x.unit_price or 0)<=maxprice)]
        if not alts:continue
        best=sorted(alts,key=lambda x:(-x.supplier.payment_terms_days,D(x.unit_price or 0),x.supplier.code))[0]
        overrides[str(item_id)]={'item_supplier_id':best.id,'supplier_id':best.supplier_id,'supplier_code':best.supplier.code}; selected.append((item_id,primary,best))
    if not overrides:return None
    cand=MPSRevisionOptimizationCandidate.objects.create(optimization_run=run,strategy=MPSRevisionOptimizationCandidate.Strategy.SUPPLIER_TERMS,name='Alternativos com prazo financeiro melhor',planning_overrides={'supplier_by_item':overrides})
    for item_id,primary,best in selected:
        MPSRevisionOptimizationAction.objects.create(candidate=cand,action_type='SUPPLIER_SWITCH',item_id=item_id,supplier_from=primary.supplier,supplier_to=best.supplier,details={'old_terms_days':primary.supplier.payment_terms_days,'new_terms_days':best.supplier.payment_terms_days,'old_unit_price':str(primary.unit_price),'new_unit_price':str(best.unit_price)})
    return cand


def _metrics(sim):
    fin=sim.financial_summary or {}; f87=fin.get('financing_087',{}); wc=fin.get('working_capital_086',{}); totals=fin.get('totals',{})
    shortages=sum(abs(num(x.delta_quantity)) for x in sim.diff_lines.filter(diff_type='SHORTAGE'))
    rccp=sim.diff_summary.get('rccp',{}) if sim.diff_summary else {}
    return {'shortage_delta_count':str(shortages),'rccp_overload_hours':str(num(rccp.get('to_overload_hours'))),'critical_rccp':int(rccp.get('to_critical') or 0),'peak_uncovered_financing':str(num((f87.get('peak_uncovered_need') or {}).get('right'))),'interest_cost':str(num((f87.get('interest_cost') or {}).get('right'))),'peak_working_capital_need':str(num((wc.get('peak_working_capital_need') or {}).get('right'))),'inventory_exposure':str(num((totals.get('INVENTORY_EXPOSURE') or {}).get('right'))),'purchase_spend':str(num((totals.get('PURCHASE_SPEND') or {}).get('right'))),'financially_feasible':bool((f87.get('financially_feasible') or {}).get('right',True))}


def _score(m,p):
    return num(m['shortage_delta_count'])*D(p.weight_shortage)+num(m['rccp_overload_hours'])*D(p.weight_rccp_overload)+num(m['peak_uncovered_financing'])/D('1000')*D(p.weight_uncovered_financing)+num(m['interest_cost'])/D('1000')*D(p.weight_interest)+num(m['inventory_exposure'])/D('1000')*D(p.weight_inventory)+num(m['purchase_spend'])/D('1000')*D(p.weight_purchase_spend)+(D('1000000') if not m['financially_feasible'] else D('0'))


def _evaluate_candidate(candidate,compare_revision,policy,user=None):
    sim=create_simulation(candidate.optimization_run.revision,compare_revision,user); sim.planning_overrides=candidate.planning_overrides or {}; sim.save(update_fields=['planning_overrides','updated_at']); run_simulation(sim)
    m=_metrics(sim); candidate.simulation=sim; candidate.metrics=m; candidate.score=_score(m,policy); candidate.save(update_fields=['simulation','metrics','score','updated_at']); return candidate


def prepare_candidates(run):
    policy,_=MPSOptimizationPolicy.objects.get_or_create(plant=run.revision.publication.cycle.plant); run.candidates.all().delete()
    base=MPSRevisionOptimizationCandidate.objects.create(optimization_run=run,strategy=MPSRevisionOptimizationCandidate.Strategy.BASELINE,name='Revisão atual',planning_overrides={})
    out=[base]
    if policy.max_candidates>1:out.append(_shift_candidate(run,MPSRevisionOptimizationCandidate.Strategy.SHIFT_LATER,1,policy.move_fraction_percent))
    if policy.max_candidates>2:out.append(_shift_candidate(run,MPSRevisionOptimizationCandidate.Strategy.SHIFT_EARLIER,-1,policy.move_fraction_percent))
    if policy.max_candidates>3:out.append(_level_candidate(run,policy.move_fraction_percent))
    return out[:policy.max_candidates]


def run_optimizer(optimization_run):
    run=MPSRevisionOptimizationRun.objects.select_related('revision__publication__cycle','compare_revision','created_by').get(pk=optimization_run.pk)
    run.status=run.Status.RUNNING; run.started_at=timezone.now(); run.error_message=''; run.save(update_fields=['status','started_at','error_message','updated_at'])
    try:
        policy,_=MPSOptimizationPolicy.objects.get_or_create(plant=run.revision.publication.cycle.plant)
        evaluated=[_evaluate_candidate(c,run.compare_revision,policy,run.created_by) for c in prepare_candidates(run)]
        supplier=_supplier_override_candidate(run,evaluated[0].simulation,policy)
        if supplier and len(evaluated)<policy.max_candidates:evaluated.append(_evaluate_candidate(supplier,run.compare_revision,policy,run.created_by))
        ranked=sorted(evaluated,key=lambda c:(c.score if c.score is not None else D('1e30'),c.id))
        for idx,c in enumerate(ranked,1):c.rank=idx;c.is_recommended=(idx==1);c.save(update_fields=['rank','is_recommended','updated_at'])
        best=ranked[0] if ranked else None
        run.summary={'candidate_count':len(ranked),'recommended_candidate_id':best.id if best else None,'recommended_strategy':best.strategy if best else None,'recommended_score':str(best.score) if best and best.score is not None else None,'objective':'Minimiza faltas, overload RCCP, necessidade financeira não coberta, juros, estoque e compras; inviabilidade financeira recebe penalidade forte.','warning':'Otimizador heurístico 0.8.8. Gera cenários para decisão humana; não publica MPS, não muda sourcing mestre e não cria OC/OP automaticamente.'}
        run.status=run.Status.COMPLETED;run.completed_at=timezone.now();run.save(update_fields=['summary','status','completed_at','updated_at']);return run
    except Exception as exc:
        run.status=run.Status.FAILED;run.error_message=str(exc);run.completed_at=timezone.now();run.save(update_fields=['status','error_message','completed_at','updated_at']);raise


@transaction.atomic
def adopt_candidate(candidate,user=None,reason=''):
    candidate=MPSRevisionOptimizationCandidate.objects.select_related('optimization_run__revision__publication').get(pk=candidate.pk)
    if candidate.strategy==MPSRevisionOptimizationCandidate.Strategy.SUPPLIER_TERMS:raise ValueError('Alternativa de fornecedor é recomendação de sourcing; aprove-a em Compras/cadastro e reexecute o plano.')
    raw=(candidate.planning_overrides or {}).get('candidate_mps_lines')
    if not raw:raise ValueError('Candidato não possui buckets MPS aplicáveis.')
    if candidate.optimization_run.status!=MPSRevisionOptimizationRun.Status.COMPLETED:raise ValueError('Otimização não concluída.')
    pub=candidate.optimization_run.revision.publication
    if pub.status not in ['DRAFT','VALIDATED','BLOCKED']:raise ValueError('Candidato só pode ser adotado antes da publicação/MRP.')
    current={(x.item_id,x.bucket_start):x for x in pub.weekly_buckets.all()}
    from datetime import date
    desired={}
    for x in raw:
        bs=date.fromisoformat(x['bucket_start']);be=date.fromisoformat(x['bucket_end']);key=(int(x['item_id']),bs);desired[key]=x
        b=current.get(key)
        if b:
            b.quantity=q(x['quantity']);b.baseline_quantity=q(x['baseline_quantity']);b.mps_status=x['mps_status'];b.frozen_reason=x.get('frozen_reason','');b.bucket_end=be;b.save(update_fields=['quantity','baseline_quantity','mps_status','frozen_reason','bucket_end','updated_at'])
        else:
            MPSWeeklyBucket.objects.create(publication=pub,item_id=x['item_id'],bucket_start=bs,bucket_end=be,quantity=q(x['quantity']),baseline_quantity=q(x['baseline_quantity']),mps_status=x['mps_status'],frozen_reason=x.get('frozen_reason',''))
    for key,b in current.items():
        if key not in desired:b.delete()
    from .sop_mps import run_rccp
    from .mps_revision import capture_revision
    run_rccp(pub)
    return capture_revision(pub,user,label=f'Adotado optimizer #{candidate.id} {candidate.strategy}',notes=reason or 'Cenário 0.8.8 adotado; requer aprovação formal.')
