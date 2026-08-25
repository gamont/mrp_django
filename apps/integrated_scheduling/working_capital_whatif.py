from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from django.db import transaction

from apps.demand.models import SalesOrder, SalesOrderLine
from apps.masterdata.models import ItemSupplier
from apps.planning.models import PlannedOrder
from .models import WorkingCapitalPolicy, MPSRevisionSimulationWorkingCapitalBucket, MPSFinancialBudget
from .mps_cashflow_whatif import _bucket_date, money, build_cashflow_impact, _purchase_unit_costs
from .mps_financial_whatif import _item_cost_map, resolve_cost_version

D=Decimal

def _schedule(raw, fallback_days):
    valid=[]
    for row in raw or []:
        try:
            days=max(0,int(row.get('days',0))); pct=D(str(row.get('percent',0)))
            if pct>0: valid.append((days,pct))
        except Exception: pass
    if not valid: return [(int(fallback_days or 0),D('100'))]
    total=sum((p for _,p in valid),D('0'))
    if total<=0: return [(int(fallback_days or 0),D('100'))]
    return [(d,p*D('100')/total) for d,p in valid]

def _sales_receivable_events(plant,start,end,bt,policy):
    invoice=defaultdict(D); receipts=defaultdict(D); weighted_days=D('0'); weighted_value=D('0'); priced=D('0'); total_open=D('0')
    qs=SalesOrderLine.objects.select_related('sales_order').filter(sales_order__plant=plant,sales_order__status__in=[SalesOrder.Status.CONFIRMED,SalesOrder.Status.PARTIAL],requested_date__lte=end)
    for line in qs:
        oq=max(D(line.quantity)-D(line.delivered_quantity),D('0'))
        if oq<=0: continue
        total_open+=oq
        if line.unit_net_price is None: continue
        value=oq*D(line.unit_net_price); priced+=oq
        # Keep contract/customer commitment semantics conservative: use line requested date in 0.8.6 projection.
        invoice_date=max(line.requested_date,start)
        invoice[_bucket_date(invoice_date,bt)]+=value
        sched=_schedule(line.sales_order.receivable_installments,line.sales_order.receivable_terms_days or policy.default_customer_terms_days)
        for days,pct in sched:
            v=value*pct/D('100'); rdate=invoice_date+timedelta(days=days)
            receipts[_bucket_date(rdate,bt)]+=v; weighted_days+=D(days)*v; weighted_value+=v
    dso=(weighted_days/weighted_value) if weighted_value else D('0')
    coverage=(priced/total_open*D('100')) if total_open else D('100')
    return invoice,receipts,dso,coverage

def _purchase_payable_events(run,plant,bt,cost_version,supplier_overrides=None):
    incurred=defaultdict(D); paid=defaultdict(D); weighted_days=D('0'); weighted_value=D('0')
    supplier_overrides=supplier_overrides or {}
    item_costs=_item_cost_map(cost_version); ids=set(run.planned_orders.filter(order_type=PlannedOrder.OrderType.PURCHASE).values_list('item_id',flat=True)); costs=_purchase_unit_costs(plant,ids,item_costs,supplier_overrides)
    prim={x.item_id:x for x in ItemSupplier.objects.select_related('supplier').filter(plant=plant,item_id__in=ids,is_primary=True).order_by('item_id','id')}
    override_ids=[int(v.get('item_supplier_id')) for v in supplier_overrides.values() if v.get('item_supplier_id')]
    for x in ItemSupplier.objects.select_related('supplier').filter(id__in=override_ids): prim[x.item_id]=x
    for po in run.planned_orders.filter(order_type=PlannedOrder.OrderType.PURCHASE):
        unit,_=costs.get(po.item_id,(D('0'),'UNVALUED')); value=D(po.quantity)*unit
        incurred[_bucket_date(po.release_date,bt)]+=value
        isup=prim.get(po.item_id); supplier=isup.supplier if isup else None
        sched=_schedule(getattr(supplier,'payment_installments',None),getattr(supplier,'payment_terms_days',0) if supplier else 0)
        for days,pct in sched:
            v=value*pct/D('100'); pdate=po.release_date+timedelta(days=days)
            paid[_bucket_date(pdate,bt)]+=v; weighted_days+=D(days)*v; weighted_value+=v
    dpo=(weighted_days/weighted_value) if weighted_value else D('0')
    return incurred,paid,dpo

def _inventory_by_bucket(sim, side):
    field='left_value' if side=='left' else 'right_value'
    return {r.bucket_date:D(getattr(r,field)) for r in sim.cashflow_buckets.filter(category='INVENTORY_VALUE')}

def _cash_out_by_bucket(sim,side):
    field='left_value' if side=='left' else 'right_value'
    return {r.bucket_date:D(getattr(r,field)) for r in sim.cashflow_buckets.filter(category='TOTAL_CASH')}

@transaction.atomic
def build_working_capital_impact(simulation,bucket_type=None):
    sim=simulation
    if not sim.target_planning_run_id or not sim.compare_planning_run_id: raise ValueError('A simulação precisa ter os dois PlanningRun concluídos.')
    if not sim.cashflow_buckets.exists(): build_cashflow_impact(sim,bucket_type=bucket_type)
    plant=sim.revision.publication.cycle.plant
    policy,_=WorkingCapitalPolicy.objects.get_or_create(plant=plant)
    start=min(sim.target_planning_run.horizon_start,sim.compare_planning_run.horizon_start); end=max(sim.target_planning_run.horizon_end,sim.compare_planning_run.horizon_end)
    cf=(sim.financial_summary or {}).get('cashflow_085',{}); bt=bucket_type or cf.get('bucket_type') or MPSFinancialBudget.BucketType.MONTHLY
    version=sim.cost_version
    if not version: version,_=resolve_cost_version(plant,start)
    invoices,receipts,dso,rev_cov=_sales_receivable_events(plant,start,end,bt,policy)
    overrides=(sim.planning_overrides or {}).get("supplier_by_item",{})
    li,lp,ldpo=_purchase_payable_events(sim.compare_planning_run,plant,bt,version); ri,rp,rdpo=_purchase_payable_events(sim.target_planning_run,plant,bt,version,overrides)
    lout=_cash_out_by_bucket(sim,'left'); rout=_cash_out_by_bucket(sim,'right'); linv=_inventory_by_bucket(sim,'left'); rinv=_inventory_by_bucket(sim,'right')
    buckets=set(invoices)|set(receipts)|set(li)|set(lp)|set(ri)|set(rp)|set(lout)|set(rout)|set(linv)|set(rinv)
    if not buckets: return {'status':'UNAVAILABLE','warning':'Sem eventos temporais para capital de giro.'}
    # taxes/freight are planning outflows at invoice bucket. Same commercial demand on both sides.
    extra_rate=(D(policy.sales_tax_percent)+D(policy.freight_percent))/D('100') if policy.include_tax_freight else D('0')
    for b,v in invoices.items():
        extra=v*extra_rate; lout[b]=lout.get(b,D('0'))+extra; rout[b]=rout.get(b,D('0'))+extra
    sim.working_capital_buckets.all().delete(); rows=[]
    lcash=rcash=D(policy.initial_cash_balance); lar=rar=lap=rap=D('0'); peak_l=peak_r=D('0'); peak_ld=peak_rd=None
    inv_values_l=[]; inv_values_r=[]
    for b in sorted(buckets):
        inv=invoices.get(b,D('0')); rec=receipts.get(b,D('0'))
        lar+=inv-rec; rar+=inv-rec
        lap+=li.get(b,D('0'))-lp.get(b,D('0')); rap+=ri.get(b,D('0'))-rp.get(b,D('0'))
        lo=lout.get(b,D('0')); ro=rout.get(b,D('0')); ln=rec-lo; rn=rec-ro; lcash+=ln; rcash+=rn
        lneed=max(D('0'),D(policy.minimum_cash_buffer)-lcash); rneed=max(D('0'),D(policy.minimum_cash_buffer)-rcash)
        if lneed>peak_l: peak_l=lneed; peak_ld=b
        if rneed>peak_r: peak_r=rneed; peak_rd=b
        liv=linv.get(b,D('0')); riv=rinv.get(b,D('0')); inv_values_l.append(liv); inv_values_r.append(riv)
        rows.append(MPSRevisionSimulationWorkingCapitalBucket(simulation=sim,bucket_date=b,left_cash_inflow=money(rec),right_cash_inflow=money(rec),left_cash_outflow=money(lo),right_cash_outflow=money(ro),left_net_cash=money(ln),right_net_cash=money(rn),left_cumulative_cash=money(lcash),right_cumulative_cash=money(rcash),left_working_capital_need=money(lneed),right_working_capital_need=money(rneed),left_ar_outstanding=money(max(D('0'),lar)),right_ar_outstanding=money(max(D('0'),rar)),left_ap_outstanding=money(max(D('0'),lap)),right_ap_outstanding=money(max(D('0'),rap)),left_inventory_value=money(liv),right_inventory_value=money(riv),details={'bucket_type':bt,'invoice_value':str(money(inv)),'tax_freight_rate_pct':str(money(extra_rate*100))}))
    MPSRevisionSimulationWorkingCapitalBucket.objects.bulk_create(rows)
    horizon_days=max(1,(end-start).days+1)
    # DIO proxy: average inventory / planned MAKE+PURCHASE value per day. Explicitly non-accounting.
    fin=(sim.financial_summary or {}).get('totals',{})
    def tv(cat,side):
        try:return D(fin.get(cat,{}).get(side,'0'))
        except:return D('0')
    avgli=sum(inv_values_l,D('0'))/D(len(inv_values_l) or 1); avgri=sum(inv_values_r,D('0'))/D(len(inv_values_r) or 1)
    lthrough=tv('MATERIAL_COST','left')+tv('PURCHASE_SPEND','left'); rthrough=tv('MATERIAL_COST','right')+tv('PURCHASE_SPEND','right')
    ldio=(avgli/(lthrough/D(horizon_days))) if lthrough>0 else D('0'); rdio=(avgri/(rthrough/D(horizon_days))) if rthrough>0 else D('0')
    out={'status':'COMPLETE','bucket_type':bt,'initial_cash_balance':str(money(policy.initial_cash_balance)),'minimum_cash_buffer':str(money(policy.minimum_cash_buffer)),'peak_working_capital_need':{'left':str(money(peak_l)),'right':str(money(peak_r)),'delta':str(money(peak_r-peak_l)),'left_date':str(peak_ld) if peak_ld else None,'right_date':str(peak_rd) if peak_rd else None},'dso_days_proxy':str(money(dso)),'dpo_days_proxy':{'left':str(money(ldpo)),'right':str(money(rdpo))},'dio_days_proxy':{'left':str(money(ldio)),'right':str(money(rdio))},'cash_conversion_cycle_proxy':{'left':str(money(ldio+dso-ldpo)),'right':str(money(rdio+dso-rdpo))},'revenue_valuation_coverage_pct':str(money(rev_cov)),'tax_percent':str(policy.sales_tax_percent),'freight_percent':str(policy.freight_percent),'warning':'Projeção gerencial de capital de giro. AR usa pedidos comerciais e preço líquido; AP usa planned PURCHASE e condição do fornecedor. DIO/DSO/DPO/CCC são proxies de planejamento, não saldos contábeis nem tesouraria real.'}
    fs=dict(sim.financial_summary or {}); fs['working_capital_086']=out; sim.financial_summary=fs; sim.save(update_fields=['financial_summary','updated_at'])
    return out
