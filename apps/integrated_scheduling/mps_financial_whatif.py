from __future__ import annotations
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_UP, ROUND_HALF_UP

from django.db.models import Q

from apps.costing.models import CostVersion, ItemCost, MovingAverageCostBalance
from apps.masterdata.models import ItemSupplier
from apps.planning.models import PlannedOrder
from .models import MPSRevisionSimulationFinancialLine

MONEY = Decimal('0.01')
QTY = Decimal('0.0001')

def money(v): return Decimal(v or 0).quantize(MONEY, rounding=ROUND_HALF_UP)
def qty(v): return Decimal(v or 0).quantize(QTY)

def resolve_cost_version(plant, as_of):
    qs=CostVersion.objects.filter(plant=plant,effective_from__lte=as_of).filter(Q(effective_to__isnull=True)|Q(effective_to__gte=as_of))
    active=qs.filter(status=CostVersion.Status.ACTIVE).order_by('-effective_from','-id').first()
    if active: return active, 'ACTIVE'
    fallback=qs.filter(status__in=[CostVersion.Status.APPROVED,CostVersion.Status.CALCULATED]).order_by('-effective_from','-id').first()
    return (fallback, 'FALLBACK_APPROVED_OR_CALCULATED') if fallback else (None, 'NO_COST_VERSION')

def _item_cost_map(version):
    if not version: return {}
    return {x.item_id:x for x in ItemCost.objects.filter(cost_version=version)}

def _purchase_unit_costs(plant, item_ids, item_costs, supplier_overrides=None):
    supplier_overrides=supplier_overrides or {}
    primary={x.item_id:x for x in ItemSupplier.objects.filter(plant=plant,item_id__in=item_ids,is_primary=True).order_by('item_id','id')}
    override_ids=[int(v.get("item_supplier_id")) for v in supplier_overrides.values() if v.get("item_supplier_id")]
    override_rows={x.id:x for x in ItemSupplier.objects.filter(id__in=override_ids)}
    mavg={x.item_id:x for x in MovingAverageCostBalance.objects.filter(plant=plant,item_id__in=item_ids)}
    out={}
    for item_id in item_ids:
        ov=supplier_overrides.get(str(item_id)) or supplier_overrides.get(item_id)
        s=override_rows.get(int(ov.get("item_supplier_id"))) if ov and ov.get("item_supplier_id") else primary.get(item_id)
        if s and s.unit_price>0:
            out[item_id]=(Decimal(s.unit_price),'OPTIMIZER_SUPPLIER' if ov else 'PRIMARY_SUPPLIER')
            continue
        b=mavg.get(item_id)
        if b and b.average_unit_cost>0:
            out[item_id]=(Decimal(b.average_unit_cost),'MOVING_AVERAGE')
            continue
        c=item_costs.get(item_id)
        if c and c.total_cost>0:
            out[item_id]=(Decimal(c.total_cost),'ITEM_COST')
            continue
        out[item_id]=(Decimal('0'),'UNVALUED')
    return out

def _last_projected(run):
    out={}
    for b in run.buckets.order_by('item_id','bucket_date').values('item_id','bucket_date','projected_available'):
        out[b['item_id']]=Decimal(b['projected_available'] or 0)
    return out

def _inventory_unit_cost(item_id, item_costs, purchase_costs):
    c=item_costs.get(item_id)
    if c and c.total_cost>0: return Decimal(c.total_cost),'ITEM_COST'
    return purchase_costs.get(item_id,(Decimal('0'),'UNVALUED'))

def _run_values(run, plant, item_costs, supplier_overrides=None):
    values=defaultdict(lambda: defaultdict(Decimal)); detail={}; unvalued=defaultdict(Decimal)
    item_ids=set(run.planned_orders.values_list('item_id',flat=True)) | set(run.buckets.values_list('item_id',flat=True))
    purchase_costs=_purchase_unit_costs(plant,item_ids,item_costs,supplier_overrides)
    for po in run.planned_orders.select_related('item'):
        q=Decimal(po.quantity)
        if po.order_type==PlannedOrder.OrderType.PURCHASE:
            unit,source=purchase_costs.get(po.item_id,(Decimal('0'),'UNVALUED'))
            v=q*unit
            values['PURCHASE_SPEND'][po.item_id]+=v
            values['CASH_OUTFLOW_PROXY'][po.item_id]+=v
            detail[('PURCHASE_SPEND',po.item_id)]={'unit_cost_source':source,'unit_cost':str(unit)}
            detail[('CASH_OUTFLOW_PROXY',po.item_id)]={'basis':'planned purchase spend; payment terms are not modeled','unit_cost_source':source}
            if unit<=0: unvalued['PURCHASE']+=q
        else:
            c=item_costs.get(po.item_id)
            if not c:
                unvalued['MAKE']+=q; continue
            comps={
                'MATERIAL_COST':Decimal(c.material_cost)+Decimal(c.subcontract_cost),
                'LABOR_COST':Decimal(c.labor_cost),
                'MACHINE_COST':Decimal(c.machine_cost),
                'OVERHEAD_COST':Decimal(c.overhead_cost)+Decimal(c.setup_cost),
                'WIP_PROXY':Decimal(c.total_cost),
            }
            for cat,unit in comps.items():
                values[cat][po.item_id]+=q*unit
                detail[(cat,po.item_id)]={'cost_version_item_cost_id':c.id,'unit_cost':str(unit)}
            detail[('WIP_PROXY',po.item_id)]['basis']='planned MAKE receipt value; proxy, not accounting WIP'
    for item_id, projected in _last_projected(run).items():
        unit,source=_inventory_unit_cost(item_id,item_costs,purchase_costs)
        values['INVENTORY_EXPOSURE'][item_id]+=max(Decimal('0'),projected)*unit
        detail[('INVENTORY_EXPOSURE',item_id)]={'basis':'end-of-horizon projected_available × valuation unit cost','unit_cost_source':source,'unit_cost':str(unit),'projected_available':str(projected)}
        if projected>0 and unit<=0: unvalued['INVENTORY']+=projected
    return values,detail,unvalued

def build_financial_impact(simulation):
    sim=simulation
    plant=sim.revision.publication.cycle.plant
    as_of=sim.revision.publication.horizon_start
    version,version_source=resolve_cost_version(plant,as_of)
    item_costs=_item_cost_map(version)
    overrides=(sim.planning_overrides or {}).get("supplier_by_item",{})
    left,left_details,left_unvalued=_run_values(sim.compare_planning_run,plant,item_costs)
    right,right_details,right_unvalued=_run_values(sim.target_planning_run,plant,item_costs,overrides)
    sim.financial_lines.all().delete()
    rows=[]; totals={}; categories=sorted(set(left)|set(right))
    for category in categories:
        lsum=Decimal('0'); rsum=Decimal('0')
        for item_id in sorted(set(left[category])|set(right[category])):
            lv=money(left[category].get(item_id,0)); rv=money(right[category].get(item_id,0)); dv=money(rv-lv)
            if lv==rv==0: continue
            rows.append(MPSRevisionSimulationFinancialLine(simulation=sim,category=category,item_id=item_id,left_value=lv,right_value=rv,delta_value=dv,
                details={'left':left_details.get((category,item_id),{}),'right':right_details.get((category,item_id),{})}))
            lsum+=lv; rsum+=rv
        totals[category]={'left':str(money(lsum)),'right':str(money(rsum)),'delta':str(money(rsum-lsum))}
    MPSRevisionSimulationFinancialLine.objects.bulk_create(rows)
    target_orders=list(sim.target_planning_run.planned_orders.values('item_id','order_type'))
    target_item_ids={x['item_id'] for x in target_orders}
    target_purchase_costs=_purchase_unit_costs(plant,target_item_ids,item_costs,overrides)
    valued_items=set()
    for x in target_orders:
        if x['order_type']==PlannedOrder.OrderType.MAKE and x['item_id'] in item_costs:
            valued_items.add(x['item_id'])
        elif x['order_type']==PlannedOrder.OrderType.PURCHASE and target_purchase_costs.get(x['item_id'],(Decimal('0'),''))[0]>0:
            valued_items.add(x['item_id'])
    coverage=Decimal('100') if not target_item_ids else Decimal(len(valued_items))*Decimal('100')/Decimal(len(target_item_ids))
    unvalued={k:str(qty(right_unvalued.get(k,0))) for k in set(left_unvalued)|set(right_unvalued) if right_unvalued.get(k,0)}
    status='COMPLETE' if not unvalued and coverage==100 else ('PARTIAL' if rows else 'UNAVAILABLE')
    summary={
        'status':status,'cost_version_id':version.id if version else None,'cost_version_code':version.code if version else None,'cost_version_source':version_source,
        'valuation_item_coverage_pct':str(coverage.quantize(Decimal('0.01'))),'unvalued_target_quantities':unvalued,'totals':totals,
        'definitions':{
            'PURCHASE_SPEND':'planned purchase quantity × supplier/moving-average/item cost',
            'CASH_OUTFLOW_PROXY':'purchase spend proxy; payment terms/tax/freight not modeled',
            'MATERIAL_COST':'MAKE quantity × rolled-up material + subcontract unit cost',
            'LABOR_COST':'MAKE quantity × rolled-up labor unit cost',
            'MACHINE_COST':'MAKE quantity × rolled-up machine unit cost',
            'OVERHEAD_COST':'MAKE quantity × rolled-up overhead + setup unit cost',
            'WIP_PROXY':'planned MAKE value; not actual accounting WIP',
            'INVENTORY_EXPOSURE':'end-horizon projected inventory × valuation unit cost',
        },
        'warning':'Valores são cenário de planejamento. Não geram lançamentos contábeis, compras, OPs ou movimentos de caixa.'
    }
    sim.cost_version=version; sim.financial_summary=summary
    sim.save(update_fields=['cost_version','financial_summary','updated_at'])
    return summary
