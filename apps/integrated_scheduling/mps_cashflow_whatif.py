from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from apps.costing.models import ItemCost
from apps.masterdata.models import ItemSupplier
from apps.planning.models import PlannedOrder
from .models import (
    MPSFinancialBudget, MPSFinancialBudgetLine,
    MPSRevisionSimulationCashFlowBucket,
)
from .mps_financial_whatif import resolve_cost_version, _item_cost_map, _purchase_unit_costs, money


def _month_start(d):
    return d.replace(day=1)


def _week_start(d):
    return d - timedelta(days=d.weekday())


def _bucket_date(d, bucket_type):
    return _week_start(d) if bucket_type == MPSFinancialBudget.BucketType.WEEKLY else _month_start(d)


def resolve_budget(plant, start, end, budget_id=None):
    qs=MPSFinancialBudget.objects.filter(plant=plant,status=MPSFinancialBudget.Status.APPROVED,period_start__lte=start,period_end__gte=end)
    if budget_id:
        return qs.filter(pk=budget_id).first()
    return qs.order_by('-period_start','-id').first()


def _primary_supplier_map(plant, item_ids, supplier_overrides=None):
    supplier_overrides=supplier_overrides or {}
    out={x.item_id:x for x in ItemSupplier.objects.select_related('supplier').filter(plant=plant,item_id__in=item_ids,is_primary=True).order_by('item_id','id')}
    ids=[int(v.get("item_supplier_id")) for v in supplier_overrides.values() if v.get("item_supplier_id")]
    for x in ItemSupplier.objects.select_related("supplier").filter(id__in=ids): out[x.item_id]=x
    return out


def _inventory_series(run, item_costs, purchase_costs, bucket_type):
    # End-of-bucket inventory valuation using the last projected_available for each item in the bucket.
    last={}
    for b in run.buckets.order_by('bucket_date','item_id').values('item_id','bucket_date','projected_available'):
        key=(_bucket_date(b['bucket_date'],bucket_type),b['item_id'])
        last[key]=Decimal(b['projected_available'] or 0)
    out=defaultdict(Decimal)
    for (bucket,item_id),q in last.items():
        c=item_costs.get(item_id)
        if c and c.total_cost>0: unit=Decimal(c.total_cost)
        else: unit=purchase_costs.get(item_id,(Decimal('0'),''))[0]
        out[bucket]+=max(Decimal('0'),q)*unit
    return out


def _run_temporal_values(run, plant, cost_version, bucket_type, supplier_overrides=None):
    values=defaultdict(lambda: defaultdict(Decimal))
    details=defaultdict(dict)
    item_costs=_item_cost_map(cost_version)
    item_ids=set(run.planned_orders.values_list('item_id',flat=True)) | set(run.buckets.values_list('item_id',flat=True))
    purchase_costs=_purchase_unit_costs(plant,item_ids,item_costs,supplier_overrides)
    suppliers=_primary_supplier_map(plant,item_ids,supplier_overrides)

    for po in run.planned_orders.select_related('item'):
        q=Decimal(po.quantity)
        if po.order_type == PlannedOrder.OrderType.PURCHASE:
            unit,source=purchase_costs.get(po.item_id,(Decimal('0'),'UNVALUED'))
            isup=suppliers.get(po.item_id)
            terms=int(isup.supplier.payment_terms_days) if isup and isup.supplier_id else 0
            payment_date=po.release_date + timedelta(days=terms)
            b=_bucket_date(payment_date,bucket_type)
            v=q*unit
            values[b]['PURCHASE_CASH']+=v
            values[b]['TOTAL_CASH']+=v
            details[(b,'PURCHASE_CASH',po.item_id)]={
                'release_date':str(po.release_date),'payment_date':str(payment_date),'payment_terms_days':terms,
                'supplier_code':isup.supplier.code if isup else None,'unit_cost_source':source,'unit_cost':str(unit),
            }
        else:
            c=item_costs.get(po.item_id)
            if not c: continue
            # Production conversion costs are timed at planned receipt/due date; material is intentionally not double-counted here.
            b=_bucket_date(po.due_date,bucket_type)
            comps={
                'LABOR':Decimal(c.labor_cost),
                'MACHINE':Decimal(c.machine_cost),
                'OVERHEAD':Decimal(c.overhead_cost)+Decimal(c.setup_cost),
            }
            for cat,unit in comps.items():
                v=q*unit; values[b][cat]+=v; values[b]['TOTAL_CASH']+=v
                details[(b,cat,po.item_id)]={'due_date':str(po.due_date),'unit_cost':str(unit),'timing_basis':'planned MAKE due date'}

    inventory=_inventory_series(run,item_costs,purchase_costs,bucket_type)
    for b,v in inventory.items(): values[b]['INVENTORY_VALUE']=v
    return values, details


@transaction.atomic
def build_cashflow_impact(simulation, budget_id=None, bucket_type=None):
    sim=simulation
    if not sim.target_planning_run_id or not sim.compare_planning_run_id:
        raise ValueError('A simulação precisa ter os dois PlanningRun concluídos.')
    plant=sim.revision.publication.cycle.plant
    start=min(sim.target_planning_run.horizon_start,sim.compare_planning_run.horizon_start)
    end=max(sim.target_planning_run.horizon_end,sim.compare_planning_run.horizon_end)
    budget=resolve_budget(plant,start,end,budget_id)
    bt=bucket_type or (budget.bucket_type if budget else MPSFinancialBudget.BucketType.MONTHLY)
    version=sim.cost_version
    if not version:
        version,_=resolve_cost_version(plant,start)
    overrides=(sim.planning_overrides or {}).get("supplier_by_item",{})
    left,left_details=_run_temporal_values(sim.compare_planning_run,plant,version,bt)
    right,right_details=_run_temporal_values(sim.target_planning_run,plant,version,bt,overrides)
    budget_map={}
    if budget:
        budget_map={(x.bucket_date,x.category):Decimal(x.amount) for x in budget.lines.all()}

    sim.cashflow_buckets.all().delete()
    rows=[]; summary=defaultdict(lambda:{'left':Decimal('0'),'right':Decimal('0'),'budget':Decimal('0'),'has_budget':False})
    buckets=sorted(set(left)|set(right)|{k[0] for k in budget_map})
    cats=['PURCHASE_CASH','LABOR','MACHINE','OVERHEAD','TOTAL_CASH','INVENTORY_VALUE']
    for b in buckets:
        for cat in cats:
            lv=money(left[b].get(cat,0)); rv=money(right[b].get(cat,0)); dv=money(rv-lv)
            bv=money(budget_map[(b,cat)]) if (b,cat) in budget_map else None
            var=money(rv-bv) if bv is not None else None
            if lv==rv==0 and bv in (None,Decimal('0.00')): continue
            rows.append(MPSRevisionSimulationCashFlowBucket(
                simulation=sim,budget=budget,bucket_date=b,category=cat,left_value=lv,right_value=rv,delta_value=dv,
                budget_value=bv,variance_to_budget=var,
                details={'bucket_type':bt,'left_detail_count':sum(1 for k in left_details if k[0]==b and k[1]==cat),'right_detail_count':sum(1 for k in right_details if k[0]==b and k[1]==cat)},
            ))
            summary[cat]['left']+=lv; summary[cat]['right']+=rv
            if bv is not None: summary[cat]['budget']+=bv; summary[cat]['has_budget']=True
    MPSRevisionSimulationCashFlowBucket.objects.bulk_create(rows)
    out={
        'bucket_type':bt,'budget_id':budget.id if budget else None,'budget_code':budget.code if budget else None,
        'cost_version_id':version.id if version else None,
        'totals':{cat:{'left':str(money(v['left'])),'right':str(money(v['right'])),'delta':str(money(v['right']-v['left'])),
                       'budget':str(money(v['budget'])) if v['has_budget'] else None,
                       'variance_to_budget':str(money(v['right']-v['budget'])) if v['has_budget'] else None}
                  for cat,v in summary.items()},
        'definitions':{
            'PURCHASE_CASH':'planned PURCHASE value timed at release_date + primary supplier payment_terms_days',
            'LABOR':'MAKE labor conversion cost timed at planned due date',
            'MACHINE':'MAKE machine conversion cost timed at planned due date',
            'OVERHEAD':'MAKE overhead + setup timed at planned due date',
            'TOTAL_CASH':'purchase cash + labor + machine + overhead; planning cash proxy, not treasury forecast',
            'INVENTORY_VALUE':'end-of-bucket projected inventory × valuation unit cost',
        },
        'warning':'Fluxo de caixa de planejamento: não considera impostos, frete, câmbio, adiantamentos, calendário bancário, faturamento real nem contas a pagar lançadas.'
    }
    fs=dict(sim.financial_summary or {}); fs['cashflow_085']=out; sim.financial_summary=fs
    sim.save(update_fields=['financial_summary','updated_at'])
    return out
