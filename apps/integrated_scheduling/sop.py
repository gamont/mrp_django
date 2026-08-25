from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q, Avg
from django.utils import timezone

from apps.demand.models import Forecast, SalesOrderLine
from apps.inventory.models import StockBalance
from apps.costing.models import MovingAverageCostBalance
from apps.masterdata.models import WorkCenter
from apps.planning.models import PlannedOrder
from apps.production.models import WorkOrderOperation
from apps.shopfloor.models import OEEPeriodSnapshot
from .models import ForecastAccuracySnapshot, ExecutiveSAndOPSnapshot, SAndOPScenario, ServiceLevelPeriodSnapshot

D0=Decimal('0')
D100=Decimal('100')

def pct(n,d):
    return (Decimal(n)*D100/Decimal(d)).quantize(Decimal('0.01')) if d else D0

def month_bounds(year, month):
    import calendar
    return date(year,month,1), date(year,month,calendar.monthrange(year,month)[1])

@transaction.atomic
def calculate_forecast_accuracy(plant, start, end):
    fc = Forecast.objects.filter(plant=plant, status=Forecast.Status.APPROVED, period_start__lte=end, period_end__gte=start)
    by_item=defaultdict(lambda: [D0,D0])
    for row in fc:
        by_item[row.item_id][0] += row.quantity
    actual = SalesOrderLine.objects.filter(sales_order__plant=plant, requested_date__range=(start,end)).exclude(sales_order__status='CANCELLED').values('item_id').annotate(q=Sum('quantity'))
    for row in actual:
        by_item[row['item_id']][1] += row['q'] or D0
    total_f=sum((v[0] for v in by_item.values()),D0); total_a=sum((v[1] for v in by_item.values()),D0)
    abs_err=sum((abs(v[0]-v[1]) for v in by_item.values()),D0)
    wape=pct(abs_err,total_a) if total_a else (D100 if total_f else D0)
    acc=max(D0,D100-wape); bias=pct(total_f-total_a,total_a) if total_a else D0
    obj,_=ForecastAccuracySnapshot.objects.update_or_create(plant=plant,period_start=start,period_end=end,defaults={
        'forecast_quantity':total_f,'actual_quantity':total_a,'absolute_error_quantity':abs_err,'wape_pct':wape,
        'forecast_accuracy_pct':acc,'bias_pct':bias,'item_count':len(by_item),'calculated_at':timezone.now(),
        'details':{'metric':'WAPE','accuracy_formula':'max(0,100-WAPE)','actual_basis':'SalesOrderLine.quantity by requested_date'} })
    return obj

def _capacity_metrics(plant,start,end):
    days=sum(1 for i in range((end-start).days+1) if (start+timedelta(days=i)).weekday()<5)
    centers=list(WorkCenter.objects.filter(plant=plant,is_active=True))
    available=sum((c.capacity_hours_per_day*c.efficiency_percent/D100*days for c in centers),D0)
    ops=WorkOrderOperation.objects.filter(work_order__plant=plant, planned_start__date__lte=end, planned_end__date__gte=start).aggregate(h=Sum('setup_hours'),r=Sum('run_hours'))
    required=(ops['h'] or D0)+(ops['r'] or D0)
    return required,available,pct(required,available)

def _backlog(plant,as_of):
    qs=SalesOrderLine.objects.select_related('sales_order').filter(sales_order__plant=plant).exclude(sales_order__status='CANCELLED')
    qty=D0; overdue=D0; value=D0; risk=D0; priced_qty=D0
    for line in qs:
        oq=max(line.quantity-line.delivered_quantity,D0)
        if not oq: continue
        qty+=oq
        if line.unit_net_price is not None:
            value += oq*line.unit_net_price; priced_qty += oq
        if line.requested_date < as_of:
            overdue += oq
            if line.unit_net_price is not None: risk += oq*line.unit_net_price
    coverage=pct(priced_qty,qty)
    return qty,overdue,value,risk,coverage

@transaction.atomic
def build_executive_snapshot(plant,start,end):
    fc=calculate_forecast_accuracy(plant,start,end)
    sl=ServiceLevelPeriodSnapshot.objects.filter(plant=plant,period_start=start,period_end=end,scope='PLANT').order_by('-calculated_at').first()
    backlog, overdue, backlog_value, risk, coverage=_backlog(plant,end+timedelta(days=1))
    inv=StockBalance.objects.filter(location__warehouse__plant=plant).aggregate(q=Sum('on_hand'))['q'] or D0
    inv_value=MovingAverageCostBalance.objects.filter(plant=plant).aggregate(v=Sum('inventory_value'))['v'] or D0
    oee=OEEPeriodSnapshot.objects.filter(machine__plant=plant,metric_date__range=(start,end)).aggregate(v=Avg('oee'))['v'] or D0
    req,avail,util=_capacity_metrics(plant,start,end)
    open_demand=D0
    for line in SalesOrderLine.objects.filter(sales_order__plant=plant,requested_date__range=(start,end)).exclude(sales_order__status='CANCELLED'):
        open_demand += max(line.quantity-line.delivered_quantity,D0)
    forecast=Forecast.objects.filter(plant=plant,status=Forecast.Status.APPROVED,period_start__lte=end,period_end__gte=start).aggregate(q=Sum('quantity'))['q'] or D0
    supply=PlannedOrder.objects.filter(planning_run__plant=plant,due_date__range=(start,end)).exclude(status='CANCELLED').aggregate(q=Sum('quantity'))['q'] or D0
    obj,_=ExecutiveSAndOPSnapshot.objects.update_or_create(plant=plant,period_start=start,period_end=end,defaults={
        'otif_pct': sl.otif_pct if sl else D0,'fill_rate_pct':sl.fill_rate_pct if sl else D0,
        'forecast_accuracy_pct':fc.forecast_accuracy_pct,'forecast_bias_pct':fc.bias_pct,
        'overdue_backlog_quantity':overdue,'backlog_value':backlog_value,'revenue_at_risk':risk,'revenue_coverage_pct':coverage,
        'inventory_quantity':inv,'inventory_value':inv_value,'oee_pct':(oee*D100).quantize(Decimal('0.01')),
        'capacity_utilization_pct':util,'open_demand_quantity':open_demand,'approved_forecast_quantity':forecast,
        'planned_supply_quantity':supply,'calculated_at':timezone.now(),
        'details':{'capacity_required_hours':str(req),'capacity_available_hours':str(avail),'backlog_quantity':str(backlog),
                   'revenue_note':'Revenue/backlog value only covers lines with unit_net_price; see revenue_coverage_pct.'}
    })
    return obj

def scenario_baseline(plant,start,end):
    snap=build_executive_snapshot(plant,start,end)
    sales=defaultdict(lambda:D0)
    for line in SalesOrderLine.objects.filter(sales_order__plant=plant,requested_date__range=(start,end)).exclude(sales_order__status='CANCELLED'):
        sales[line.item_id] += max(line.quantity-line.delivered_quantity,D0)
    forecasts=defaultdict(lambda:D0)
    for row in Forecast.objects.filter(plant=plant,status=Forecast.Status.APPROVED,period_start__lte=end,period_end__gte=start): forecasts[row.item_id]+=row.quantity
    demand=sum((max(sales[k],forecasts[k]) for k in set(sales)|set(forecasts)),D0)
    inventory_available=StockBalance.objects.filter(location__warehouse__plant=plant).aggregate(q=Sum('on_hand'),a=Sum('allocated'))
    avail=(inventory_available['q'] or D0)-(inventory_available['a'] or D0)
    return {'demand_plan_qty':str(demand),'open_demand_qty':str(snap.open_demand_quantity),'forecast_qty':str(snap.approved_forecast_quantity),
            'planned_supply_qty':str(snap.planned_supply_quantity),'inventory_available_qty':str(avail),
            'capacity_utilization_pct':str(snap.capacity_utilization_pct),'otif_pct':str(snap.otif_pct),'oee_pct':str(snap.oee_pct),
            'revenue_at_risk':str(snap.revenue_at_risk),'revenue_coverage_pct':str(snap.revenue_coverage_pct)}

@transaction.atomic
def simulate_sop_scenario(scenario):
    b=scenario_baseline(scenario.plant,scenario.horizon_start,scenario.horizon_end)
    d=Decimal(b['demand_plan_qty'])*(D100+scenario.demand_change_pct)/D100
    inv=Decimal(b['inventory_available_qty'])*(D100+scenario.inventory_change_pct)/D100
    supply=Decimal(b['planned_supply_qty'])
    util=Decimal(b['capacity_utilization_pct'])
    new_util=util*(D100+scenario.demand_change_pct)/(D100+scenario.capacity_change_pct) if (D100+scenario.capacity_change_pct)!=0 else Decimal('999')
    gap=max(d-inv-supply,D0)
    simulated={'demand_plan_qty':str(d.quantize(Decimal('0.0001'))),'inventory_available_qty':str(inv.quantize(Decimal('0.0001'))),
               'planned_supply_qty':str(supply),'projected_supply_gap_qty':str(gap.quantize(Decimal('0.0001'))),
               'capacity_utilization_pct':str(new_util.quantize(Decimal('0.01'))),
               'capacity_overload':bool(new_util>100),'assumption':'Executive aggregate what-if; does not replace MRP/CP-SAT execution.'}
    scenario.baseline=b; scenario.simulated=simulated; scenario.status=SAndOPScenario.Status.SIMULATED
    scenario.save(update_fields=['baseline','simulated','status','updated_at'])
    return scenario
