from __future__ import annotations
from collections import defaultdict
from decimal import Decimal
from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from .models import (
    OperationalMPSPublication, MPSWeeklyBucket, MPSRevision, MPSRevisionLine,
    MPSRevisionRCCPLine, MPSRCCPException,
)
from .sop_mps import run_rccp

Q=Decimal("0.0001")
def q(v): return Decimal(v or 0).quantize(Q)

def _next_number(pub):
    return (pub.revisions.aggregate(v=Max("number"))["v"] or 0)+1

def revision_metrics(revision):
    lines=list(revision.lines.all())
    total=sum((q(x.quantity) for x in lines),Decimal(0))
    changed=sum(1 for x in lines if q(x.quantity)!=q(x.baseline_quantity))
    delta=sum((abs(q(x.quantity)-q(x.baseline_quantity)) for x in lines),Decimal(0))
    rccp=list(revision.rccp_lines.all())
    overload=sum((q(x.overload_hours) for x in rccp),Decimal(0))
    critical=sum(1 for x in rccp if x.severity==MPSRCCPException.Severity.CRITICAL and x.overload_hours>0)
    return {"buckets":len(lines),"quantity":str(q(total)),"changed_buckets":changed,"absolute_quantity_delta":str(q(delta)),"rccp_overload_hours":str(q(overload)),"critical_rccp":critical}

@transaction.atomic
def capture_revision(pub, user=None, kind=MPSRevision.Kind.WORKING, label="", notes="", auto_approve=False):
    pub=OperationalMPSPublication.objects.select_for_update().get(pk=pub.pk)
    parent=pub.revisions.order_by("-number").first()
    rev=MPSRevision.objects.create(publication=pub,number=_next_number(pub),parent=parent,kind=kind,status=MPSRevision.Status.APPROVED if auto_approve else MPSRevision.Status.DRAFT,label=label,notes=notes,created_by=user,approved_by=user if auto_approve else None,approved_at=timezone.now() if auto_approve else None)
    MPSRevisionLine.objects.bulk_create([MPSRevisionLine(revision=rev,item=b.item,bucket_start=b.bucket_start,bucket_end=b.bucket_end,quantity=b.quantity,baseline_quantity=b.baseline_quantity,mps_status=b.mps_status,frozen_reason=b.frozen_reason) for b in pub.weekly_buckets.select_related("item")])
    MPSRevisionRCCPLine.objects.bulk_create([MPSRevisionRCCPLine(revision=rev,work_center=e.work_center,bucket_start=e.bucket_start,required_hours=e.required_hours,available_hours=e.available_hours,overload_hours=e.overload_hours,overload_percent=e.overload_percent,severity=e.severity) for e in pub.rccp_exceptions.select_related("work_center")])
    rev.summary=revision_metrics(rev)
    baseline=pub.revisions.filter(kind=MPSRevision.Kind.BASELINE).exclude(pk=rev.pk).order_by("number").first()
    if baseline:
        diff=compare_revisions(baseline,rev)
        rev.mrp_impact_summary=diff["estimated_mrp_impact"]
        rev.rccp_summary=diff["rccp_impact"]
    else:
        rev.mrp_impact_summary={"changed_buckets":0,"changed_items":0,"net_quantity_delta":"0.0000","absolute_quantity_delta":"0.0000","note":"Estimativa pré-MRP; não substitui netting detalhado."}
        rev.rccp_summary={"overload_hours_delta":"0.0000","critical_delta":0}
    rev.save(update_fields=["summary","mrp_impact_summary","rccp_summary","updated_at"])
    return rev

def compare_revisions(left, right):
    L={(x.item_id,x.bucket_start):x for x in left.lines.all()}
    R={(x.item_id,x.bucket_start):x for x in right.lines.all()}
    keys=sorted(set(L)|set(R),key=lambda k:(k[1],k[0]))
    rows=[]; changed_items=set(); net=Decimal(0); absolute=Decimal(0); frozen=0
    for key in keys:
        a=L.get(key); b=R.get(key); aq=q(a.quantity if a else 0); bq=q(b.quantity if b else 0); d=q(bq-aq)
        if d or (a and b and a.mps_status!=b.mps_status):
            item=(b or a).item; changed_items.add(item.pk); net+=d; absolute+=abs(d)
            if (a and a.mps_status=="FROZEN") or (b and b.mps_status=="FROZEN"): frozen+=1
            rows.append({"item_id":item.pk,"item_code":item.code,"bucket_start":str(key[1]),"from_quantity":str(aq),"to_quantity":str(bq),"delta":str(d),"from_status":a.mps_status if a else None,"to_status":b.mps_status if b else None})
    lmet=revision_metrics(left); rmet=revision_metrics(right)
    rccp={"from_overload_hours":lmet["rccp_overload_hours"],"to_overload_hours":rmet["rccp_overload_hours"],"overload_hours_delta":str(q(Decimal(rmet["rccp_overload_hours"])-Decimal(lmet["rccp_overload_hours"]))),"from_critical":lmet["critical_rccp"],"to_critical":rmet["critical_rccp"],"critical_delta":rmet["critical_rccp"]-lmet["critical_rccp"]}
    mrp={"changed_buckets":len(rows),"changed_items":len(changed_items),"frozen_buckets_changed":frozen,"net_quantity_delta":str(q(net)),"absolute_quantity_delta":str(q(absolute)),"note":"Impacto estimado antes do MRP: mede alterações do MPS; componentes, netting e ordens só são conhecidos após executar o MRP."}
    return {"from_revision":left.number,"to_revision":right.number,"rows":rows,"rccp_impact":rccp,"estimated_mrp_impact":mrp}

@transaction.atomic
def submit_revision(revision,user=None):
    if revision.status!=MPSRevision.Status.DRAFT: raise ValueError("Somente revisão DRAFT pode ser submetida.")
    revision.status=MPSRevision.Status.PENDING_APPROVAL; revision.submitted_by=user; revision.submitted_at=timezone.now(); revision.save(update_fields=["status","submitted_by","submitted_at","updated_at"]); return revision

@transaction.atomic
def approve_revision(revision,user=None,notes=""):
    revision=MPSRevision.objects.select_for_update().select_related("publication__policy").get(pk=revision.pk)
    if revision.status!=MPSRevision.Status.PENDING_APPROVAL: raise ValueError("Revisão não está aguardando aprovação.")
    if user and revision.created_by_id and revision.created_by_id==getattr(user,"id",None): raise ValueError("O autor da revisão não pode aprovar a própria revisão.")
    if revision.kind != MPSRevision.Kind.BASELINE and revision.publication.policy.require_mrp_whatif_before_approval:
        if not revision.mrp_simulations.filter(status="COMPLETED").exists():
            raise ValueError("A política do MPS exige uma simulação MRP what-if concluída antes da aprovação da revisão.")
    if revision.kind != MPSRevision.Kind.BASELINE:
        from .models import MPSOptimizationPolicy
        opt_policy=MPSOptimizationPolicy.objects.filter(plant=revision.publication.cycle.plant).first()
        if opt_policy and opt_policy.require_optimizer_before_approval:
            if not revision.optimization_runs.filter(status="COMPLETED").exists():
                raise ValueError("A política 0.8.8 exige uma otimização MPS concluída antes da aprovação da revisão.")
    if revision.kind != MPSRevision.Kind.BASELINE:
        from .models import FinancingPolicy
        fin_policy = FinancingPolicy.objects.filter(plant=revision.publication.cycle.plant).first()
        if fin_policy and fin_policy.block_revision_approval_when_exceeded:
            sim = revision.mrp_simulations.filter(status="COMPLETED").order_by("-created_at").first()
            fin = ((sim.financial_summary or {}).get("financing_087", {}) if sim else {})
            if not fin:
                raise ValueError("A política financeira exige simulação de financiamento 0.8.7 antes da aprovação.")
            if not fin.get("financially_feasible", {}).get("right", False):
                uncovered = fin.get("peak_uncovered_need", {}).get("right", "0")
                raise ValueError(f"Revisão excede a capacidade financeira da planta. Necessidade não coberta: {uncovered}.")
    revision.publication.revisions.filter(status=MPSRevision.Status.APPROVED).exclude(pk=revision.pk).update(status=MPSRevision.Status.SUPERSEDED)
    revision.status=MPSRevision.Status.APPROVED; revision.approved_by=user; revision.approved_at=timezone.now(); revision.decision_notes=notes; revision.save(update_fields=["status","approved_by","approved_at","decision_notes","updated_at"]); return revision

@transaction.atomic
def reject_revision(revision,user=None,notes=""):
    if revision.status!=MPSRevision.Status.PENDING_APPROVAL: raise ValueError("Revisão não está aguardando aprovação.")
    revision.status=MPSRevision.Status.REJECTED; revision.approved_by=user; revision.approved_at=timezone.now(); revision.decision_notes=notes; revision.save(update_fields=["status","approved_by","approved_at","decision_notes","updated_at"]); return revision

@transaction.atomic
def rollback_to_revision(pub, target, user=None, reason=""):
    if target.publication_id!=pub.id: raise ValueError("Revisão pertence a outra publicação.")
    if pub.status not in [OperationalMPSPublication.Status.DRAFT,OperationalMPSPublication.Status.VALIDATED,OperationalMPSPublication.Status.BLOCKED]: raise ValueError("Rollback só é permitido antes da publicação/MRP.")
    by={(x.item_id,x.bucket_start):x for x in target.lines.select_related("item")}
    for b in pub.weekly_buckets.all():
        x=by.get((b.item_id,b.bucket_start))
        if x:
            b.quantity=x.quantity; b.baseline_quantity=x.baseline_quantity; b.mps_status=x.mps_status; b.frozen_reason=x.frozen_reason; b.save(update_fields=["quantity","baseline_quantity","mps_status","frozen_reason","updated_at"] )
        else: b.delete()
    existing={(b.item_id,b.bucket_start) for b in pub.weekly_buckets.all()}
    MPSWeeklyBucket.objects.bulk_create([MPSWeeklyBucket(publication=pub,item=x.item,bucket_start=x.bucket_start,bucket_end=x.bucket_end,quantity=x.quantity,baseline_quantity=x.baseline_quantity,mps_status=x.mps_status,frozen_reason=x.frozen_reason) for x in target.lines.select_related("item") if (x.item_id,x.bucket_start) not in existing])
    run_rccp(pub)
    return capture_revision(pub,user,kind=MPSRevision.Kind.ROLLBACK,label=f"Rollback para r{target.number}",notes=reason)

def latest_revision(pub):
    return pub.revisions.order_by("-number").first()
