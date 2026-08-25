from __future__ import annotations
from collections import defaultdict
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.planning.models import PlanningRun, PlannedOrder, PlanningMessage, PeggingRecord
from apps.planning.services import execute_planning_run
from .models import MPSRevision, MPSRevisionSimulation, MPSRevisionSimulationDiffLine
from .mps_revision import compare_revisions

Q=Decimal("0.0001")
def q(v): return Decimal(v or 0).quantize(Q)

def _inline_mps(revision):
    return [
        {"item_id":x.item_id,"due_date":x.bucket_start.isoformat(),"quantity":str(q(x.quantity)),"source_id":x.id,"source_model":"MPSRevisionLine"}
        for x in revision.lines.all() if x.quantity>0
    ]

def _create_run(revision, label, planning_overrides=None):
    pub=revision.publication
    planning_overrides=planning_overrides or {}
    inline=planning_overrides.get("inline_mps_demands") or _inline_mps(revision)
    return PlanningRun.objects.create(
        name=f"WHATIF {pub.source} r{revision.number} {label}", plant=pub.cycle.plant,
        horizon_start=pub.horizon_start, horizon_end=pub.horizon_end,
        parameters={"source":"MPS_REVISION_WHATIF","mps_revision_id":revision.id,
                    "inline_mps_demands":inline,
                    "planning_overrides":planning_overrides,
                    "include_sales_orders":False,"include_forecasts":False,"what_if":True},
    )

def _order_map(run, order_type):
    out=defaultdict(Decimal)
    for r in run.planned_orders.filter(order_type=order_type).values("item_id","due_date").annotate(total=Sum("quantity")):
        out[(r["item_id"],r["due_date"])]+=q(r["total"])
    return out

def _shortage_map(run):
    out=defaultdict(Decimal); detail={}
    qs=run.messages.filter(message_type__in=[PlanningMessage.MessageType.SHORTAGE,PlanningMessage.MessageType.PAST_DUE,PlanningMessage.MessageType.RESCHEDULE_IN,PlanningMessage.MessageType.RESCHEDULE_OUT])
    for m in qs.select_related("item"):
        k=(m.item_id,m.action_date or m.suggested_date,m.message_type)
        out[k]+=Decimal(1); detail[k]=m.message
    return out,detail

def _pegging_map(run):
    out=defaultdict(Decimal)
    for r in run.pegging_records.values("component_item_id","top_level_item_id","requirement_date").annotate(total=Sum("quantity")):
        out[(r["component_item_id"],r["top_level_item_id"],r["requirement_date"])]+=q(r["total"])
    return out

def _append_diff(sim, kind, left, right, key_builder, item_pos=0, date_pos=1, details_fn=None):
    keys=set(left)|set(right); rows=[]; changed=0; abs_delta=Decimal(0)
    for k in keys:
        lv=q(left.get(k,0)); rv=q(right.get(k,0)); d=q(rv-lv)
        if not d: continue
        changed+=1; abs_delta+=abs(d)
        rows.append(MPSRevisionSimulationDiffLine(simulation=sim,diff_type=kind,item_id=k[item_pos] if k[item_pos] else None,
            event_date=k[date_pos] if date_pos is not None else None,reference_key=key_builder(k),left_quantity=lv,right_quantity=rv,delta_quantity=d,
            details=(details_fn(k) if details_fn else {})))
    MPSRevisionSimulationDiffLine.objects.bulk_create(rows)
    return {"changed":changed,"absolute_delta":str(q(abs_delta))}

@transaction.atomic
def create_simulation(revision, compare_revision=None, user=None):
    if compare_revision is None:
        compare_revision=revision.publication.revisions.filter(kind=MPSRevision.Kind.BASELINE).order_by("number").first() or revision.parent
    if not compare_revision: raise ValueError("Não existe revisão de comparação.")
    if compare_revision.publication_id!=revision.publication_id: raise ValueError("As revisões devem pertencer ao mesmo MPS operacional.")
    return MPSRevisionSimulation.objects.create(revision=revision,compare_revision=compare_revision,created_by=user)

def run_simulation(simulation):
    sim=MPSRevisionSimulation.objects.select_related("revision__publication__cycle","compare_revision").get(pk=simulation.pk)
    sim.status=MPSRevisionSimulation.Status.RUNNING; sim.started_at=timezone.now(); sim.error_message=""; sim.save(update_fields=["status","started_at","error_message","updated_at"])
    try:
        left_run=_create_run(sim.compare_revision,"BASE"); execute_planning_run(left_run)
        right_run=_create_run(sim.revision,"TARGET",sim.planning_overrides); execute_planning_run(right_run)
        sim.diff_lines.all().delete()
        make=_append_diff(sim,MPSRevisionSimulationDiffLine.DiffType.MAKE,_order_map(left_run,PlannedOrder.OrderType.MAKE),_order_map(right_run,PlannedOrder.OrderType.MAKE),lambda k:f"MAKE:{k[0]}:{k[1]}")
        purch=_append_diff(sim,MPSRevisionSimulationDiffLine.DiffType.PURCHASE,_order_map(left_run,PlannedOrder.OrderType.PURCHASE),_order_map(right_run,PlannedOrder.OrderType.PURCHASE),lambda k:f"PURCHASE:{k[0]}:{k[1]}")
        ls,ld=_shortage_map(left_run); rs,rd=_shortage_map(right_run)
        short=_append_diff(sim,MPSRevisionSimulationDiffLine.DiffType.SHORTAGE,ls,rs,lambda k:f"SHORTAGE:{k[0]}:{k[1]}:{k[2]}",details_fn=lambda k:{"message_type":k[2],"left_message":ld.get(k,""),"right_message":rd.get(k,"")})
        peg=_append_diff(sim,MPSRevisionSimulationDiffLine.DiffType.PEGGING,_pegging_map(left_run),_pegging_map(right_run),lambda k:f"PEG:{k[0]}:{k[1]}:{k[2]}",date_pos=2,details_fn=lambda k:{"top_level_item_id":k[1]})
        rccp=compare_revisions(sim.compare_revision,sim.revision)["rccp_impact"]
        sim.target_planning_run=right_run; sim.compare_planning_run=left_run
        sim.summary={"target":{"planned_orders":right_run.planned_orders.count(),"make":right_run.planned_orders.filter(order_type="MAKE").count(),"purchase":right_run.planned_orders.filter(order_type="PURCHASE").count(),"messages":right_run.messages.count(),"pegging_records":right_run.pegging_records.count()},"compare":{"planned_orders":left_run.planned_orders.count(),"make":left_run.planned_orders.filter(order_type="MAKE").count(),"purchase":left_run.planned_orders.filter(order_type="PURCHASE").count(),"messages":left_run.messages.count(),"pegging_records":left_run.pegging_records.count()}}
        sim.diff_summary={"make":make,"purchase":purch,"shortages":short,"pegging":peg,"rccp":rccp,"note":"WHAT-IF: compara recomendações MRP (planned orders), mensagens/pegging e RCCP; não cria OCs/OPs reais."}
        from .mps_financial_whatif import build_financial_impact
        build_financial_impact(sim)
        from .mps_cashflow_whatif import build_cashflow_impact
        build_cashflow_impact(sim)
        from .working_capital_whatif import build_working_capital_impact
        build_working_capital_impact(sim)
        from .financing_whatif import build_financing_impact
        build_financing_impact(sim)
        sim.refresh_from_db(fields=["financial_summary", "cost_version"])
        sim.diff_summary["financial"] = sim.financial_summary
        sim.status=MPSRevisionSimulation.Status.COMPLETED; sim.completed_at=timezone.now()
        sim.save(update_fields=["target_planning_run","compare_planning_run","summary","diff_summary","status","completed_at","updated_at"])
        sim.revision.mrp_impact_summary={**(sim.revision.mrp_impact_summary or {}),"what_if_simulation_id":sim.id,"what_if":sim.diff_summary}
        sim.revision.save(update_fields=["mrp_impact_summary","updated_at"])
        return sim
    except Exception as exc:
        sim.status=MPSRevisionSimulation.Status.FAILED; sim.error_message=str(exc); sim.completed_at=timezone.now(); sim.save(update_fields=["status","error_message","completed_at","updated_at"]); raise

def latest_completed_simulation(revision):
    return revision.mrp_simulations.filter(status=MPSRevisionSimulation.Status.COMPLETED).order_by("-created_at").first()
