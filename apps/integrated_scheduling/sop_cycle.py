from __future__ import annotations
from collections import defaultdict
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.demand.models import Forecast, MasterProductionSchedule, SalesOrder, SalesOrderLine
from apps.inventory.models import StockBalance
from apps.masterdata.models import Item
from apps.planning.models import PlannedOrder, PlanningRun
from .models import (
    ExecutiveSAndOPSnapshot, SAndOPCycle, SAndOPDemandConsensusLine,
    SAndOPSupplyPlanLine, SAndOPConstraint, SAndOPDecision, SAndOPPublication,
)

ZERO = Decimal("0")
Q = Decimal("0.0001")


def q(v):
    return Decimal(v or 0).quantize(Q)


def month_start(d: date) -> date:
    return d.replace(day=1)


def next_month(d: date) -> date:
    return date(d.year + (1 if d.month == 12 else 0), 1 if d.month == 12 else d.month + 1, 1)


def iter_months(start: date, end: date):
    cur = month_start(start)
    while cur <= end:
        yield cur
        cur = next_month(cur)


@transaction.atomic
def create_sop_cycle(plant, cycle_month: date, horizon_end: date, user=None, meeting_date=None):
    cycle_month = month_start(cycle_month)
    code = f"SOP-{cycle_month:%Y-%m}"
    last = SAndOPCycle.objects.filter(plant=plant, code=code).order_by("-version").first()
    version = (last.version + 1) if last else 1
    snap = ExecutiveSAndOPSnapshot.objects.filter(plant=plant, period_start__lte=cycle_month, period_end__gte=cycle_month).order_by("-calculated_at").first()
    cycle = SAndOPCycle.objects.create(
        plant=plant, code=code, version=version, cycle_month=cycle_month,
        horizon_start=cycle_month, horizon_end=horizon_end, meeting_date=meeting_date,
        source_snapshot=snap, created_by=user,
    )
    refresh_demand_baseline(cycle)
    return cycle


@transaction.atomic
def refresh_demand_baseline(cycle: SAndOPCycle):
    if cycle.status not in [SAndOPCycle.Status.DRAFT, SAndOPCycle.Status.DEMAND_REVIEW]:
        raise ValueError("Baseline de demanda só pode ser atualizado antes do Supply Review.")
    cycle.demand_lines.all().delete()
    data = defaultdict(lambda: {"forecast": ZERO, "orders": ZERO})
    forecasts = Forecast.objects.filter(
        plant=cycle.plant, status=Forecast.Status.APPROVED,
        period_start__lte=cycle.horizon_end, period_end__gte=cycle.horizon_start,
    )
    for row in forecasts:
        bucket = month_start(max(row.period_start, cycle.horizon_start))
        data[(row.item_id, bucket)]["forecast"] += row.quantity
    orders = SalesOrderLine.objects.filter(
        sales_order__plant=cycle.plant,
        sales_order__status__in=[SalesOrder.Status.CONFIRMED, SalesOrder.Status.PARTIAL],
        requested_date__range=(cycle.horizon_start, cycle.horizon_end),
    ).annotate(open_qty=F("quantity") - F("delivered_quantity"))
    for row in orders:
        if row.open_qty > 0:
            data[(row.item_id, month_start(row.requested_date))]["orders"] += row.open_qty
    lines=[]
    total_f=total_o=total_c=ZERO
    for (item_id,bucket), vals in sorted(data.items(), key=lambda x:(x[0][1],x[0][0])):
        consensus=max(vals["forecast"], vals["orders"])
        lines.append(SAndOPDemandConsensusLine(
            cycle=cycle,item_id=item_id,bucket_date=bucket,
            baseline_forecast_quantity=q(vals["forecast"]),open_order_quantity=q(vals["orders"]),
            consensus_quantity=q(consensus),
        ))
        total_f+=vals["forecast"]; total_o+=vals["orders"]; total_c+=consensus
    SAndOPDemandConsensusLine.objects.bulk_create(lines)
    cycle.demand_baseline={"forecast_quantity":str(q(total_f)),"open_order_quantity":str(q(total_o)),"default_consensus_rule":"max(forecast, open orders)","line_count":len(lines)}
    cycle.demand_consensus_summary={"consensus_quantity":str(q(total_c)),"line_count":len(lines)}
    if cycle.status == SAndOPCycle.Status.DRAFT:
        cycle.status=SAndOPCycle.Status.DEMAND_REVIEW
    cycle.save(update_fields=["demand_baseline","demand_consensus_summary","status","updated_at"])
    return cycle


@transaction.atomic
def update_consensus_line(line: SAndOPDemandConsensusLine, adjustment, rationale=""):
    if line.cycle.status != SAndOPCycle.Status.DEMAND_REVIEW:
        raise ValueError("Consenso só pode ser ajustado durante Demand Review.")
    line.commercial_adjustment_quantity=q(adjustment)
    line.consensus_quantity=q(max(line.baseline_forecast_quantity,line.open_order_quantity)+line.commercial_adjustment_quantity)
    if line.consensus_quantity < 0: line.consensus_quantity=ZERO
    line.rationale=rationale
    line.save(update_fields=["commercial_adjustment_quantity","consensus_quantity","rationale","updated_at"])
    total=line.cycle.demand_lines.aggregate(v=Sum("consensus_quantity"))["v"] or ZERO
    line.cycle.demand_consensus_summary={"consensus_quantity":str(q(total)),"line_count":line.cycle.demand_lines.count()}
    line.cycle.save(update_fields=["demand_consensus_summary","updated_at"])
    return line


@transaction.atomic
def build_supply_review(cycle: SAndOPCycle):
    if cycle.status not in [SAndOPCycle.Status.DEMAND_REVIEW, SAndOPCycle.Status.SUPPLY_REVIEW]:
        raise ValueError("Supply Review requer Demand Review concluído.")
    cycle.supply_lines.all().delete()
    stock={r["item_id"]: (r["q"] or ZERO) for r in StockBalance.objects.filter(location__warehouse__plant=cycle.plant).values("item_id").annotate(q=Sum("on_hand"))}
    planned=defaultdict(Decimal)
    po=PlannedOrder.objects.filter(planning_run__plant=cycle.plant,due_date__range=(cycle.horizon_start,cycle.horizon_end)).exclude(status=PlannedOrder.Status.CANCELLED)
    for row in po:
        planned[(row.item_id,month_start(row.due_date))]+=row.quantity
    running_inventory=defaultdict(Decimal, stock)
    out=[]; total_gap=total_supply=ZERO
    for line in cycle.demand_lines.select_related("item").order_by("bucket_date","item__code"):
        opening=running_inventory[line.item_id]
        supply=planned[(line.item_id,line.bucket_date)]
        constrained=supply
        end=opening+constrained-line.consensus_quantity
        gap=max(-end,ZERO)
        projected=max(end,ZERO)
        running_inventory[line.item_id]=projected
        out.append(SAndOPSupplyPlanLine(cycle=cycle,item_id=line.item_id,bucket_date=line.bucket_date,
            demand_quantity=line.consensus_quantity,opening_inventory_quantity=q(opening),planned_supply_quantity=q(supply),
            capacity_constrained_quantity=q(constrained),projected_ending_inventory_quantity=q(projected),gap_quantity=q(gap)))
        total_gap+=gap; total_supply+=supply
    SAndOPSupplyPlanLine.objects.bulk_create(out)
    cycle.supply_summary={"planned_supply_quantity":str(q(total_supply)),"gap_quantity":str(q(total_gap)),"line_count":len(out)}
    cycle.status=SAndOPCycle.Status.SUPPLY_REVIEW
    cycle.save(update_fields=["supply_summary","status","updated_at"])
    return cycle


def summarize_constraints(cycle):
    open_qs=cycle.constraints_register.exclude(status=SAndOPConstraint.Status.CLOSED)
    by_severity={s:open_qs.filter(severity=s).count() for s,_ in SAndOPConstraint.Severity.choices}
    cycle.constraints_summary={"open":open_qs.count(),"by_severity":by_severity,"critical":by_severity.get("CRITICAL",0)}
    cycle.save(update_fields=["constraints_summary","updated_at"])
    return cycle.constraints_summary


@transaction.atomic
def advance_cycle(cycle: SAndOPCycle):
    transition={
        SAndOPCycle.Status.SUPPLY_REVIEW:SAndOPCycle.Status.PRE_SOP,
        SAndOPCycle.Status.PRE_SOP:SAndOPCycle.Status.EXECUTIVE_REVIEW,
    }
    nxt=transition.get(cycle.status)
    if not nxt: raise ValueError(f"Não há avanço automático a partir de {cycle.status}.")
    summarize_constraints(cycle)
    cycle.status=nxt; cycle.save(update_fields=["status","updated_at"])
    return cycle


@transaction.atomic
def approve_cycle(cycle: SAndOPCycle, user=None):
    if cycle.status != SAndOPCycle.Status.EXECUTIVE_REVIEW:
        raise ValueError("Somente um ciclo em Executive Review pode ser aprovado.")
    critical=cycle.constraints_register.filter(status=SAndOPConstraint.Status.OPEN,severity=SAndOPConstraint.Severity.CRITICAL).count()
    if critical:
        raise ValueError("Existem restrições críticas abertas; mitigue/aceite antes da aprovação.")
    cycle.executive_summary={"decisions":cycle.decisions.count(),"open_decisions":cycle.decisions.filter(status=SAndOPDecision.Status.OPEN).count(),"approved_at":timezone.now().isoformat()}
    cycle.status=SAndOPCycle.Status.APPROVED; cycle.approved_by=user; cycle.approved_at=timezone.now()
    cycle.save(update_fields=["executive_summary","status","approved_by","approved_at","updated_at"])
    return cycle


@transaction.atomic
def publish_cycle_to_mps(cycle: SAndOPCycle, user=None, create_planning_run=True):
    if cycle.status != SAndOPCycle.Status.APPROVED:
        raise ValueError("Somente ciclo S&OP aprovado pode ser publicado.")
    source=f"SOP:{cycle.code}:v{cycle.version}"
    MasterProductionSchedule.objects.filter(plant=cycle.plant,source=source).delete()
    count=0
    for line in cycle.supply_lines.select_related("item"):
        qty=line.capacity_constrained_quantity
        if qty <= 0:
            # sem suprimento calculado, publica a necessidade de consenso para que o MRP faça netting detalhado
            qty=line.demand_quantity
        if qty <= 0: continue
        MasterProductionSchedule.objects.create(
            plant=cycle.plant,item=line.item,due_date=line.bucket_date,quantity=q(qty),
            status=MasterProductionSchedule.Status.FIRM,source=source,
            notes=f"Publicado pelo ciclo {cycle.code} v{cycle.version}."
        ); count+=1
    run=None
    if create_planning_run:
        run=PlanningRun.objects.create(name=f"MRP from {cycle.code} v{cycle.version}",plant=cycle.plant,
            horizon_start=cycle.horizon_start,horizon_end=cycle.horizon_end,
            parameters={"source":"SOP","sop_cycle_id":cycle.id,"include_sales_orders":False,"include_forecasts":False})
    pub,_=SAndOPPublication.objects.update_or_create(cycle=cycle,defaults={"mps_source":source,"mps_lines":count,"planning_run":run,"published_by":user,"published_at":timezone.now(),"details":{"planning_run_created":bool(run)}})
    SAndOPCycle.objects.filter(plant=cycle.plant,code=cycle.code,status=SAndOPCycle.Status.PUBLISHED).exclude(pk=cycle.pk).update(status=SAndOPCycle.Status.ARCHIVED)
    cycle.status=SAndOPCycle.Status.PUBLISHED; cycle.published_by=user; cycle.published_at=timezone.now(); cycle.published_planning_run=run
    cycle.save(update_fields=["status","published_by","published_at","published_planning_run","updated_at"])
    return pub
