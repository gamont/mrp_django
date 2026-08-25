from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.services import append_domain_event
from apps.masterdata.models import BOMLine
from apps.planning.models import PlannedOrder, PlanningChange
from apps.production.models import WorkOrder

from .models import BOMRevision, EngineeringChange, EngineeringImpact


def _event(change, event_type, actor=None, extra=None):
    return append_domain_event(idempotency_key=f"eco:{change.pk}:{event_type}:{change.updated_at.isoformat()}", event_type=event_type, aggregate_type="EngineeringChange", aggregate_id=str(change.pk), payload={"number": change.number, "status": change.status, **(extra or {})}, actor=actor)


@transaction.atomic
def analyze_impact(change: EngineeringChange, actor=None):
    change = EngineeringChange.objects.select_for_update().get(pk=change.pk)
    EngineeringImpact.objects.filter(change=change).delete()
    item_ids = list(change.items.values_list("affected_item_id", flat=True))
    impacts=[]
    for line in BOMLine.objects.filter(component_id__in=item_ids, is_active=True).select_related("parent", "component"):
        impacts.append(EngineeringImpact(change=change, impact_type="WHERE_USED", object_type="BOMLine", object_id=str(line.pk), severity="HIGH", description=f"{line.component.code} é usado em {line.parent.code}", details={"parent": line.parent.code, "component": line.component.code}))
    for order in WorkOrder.objects.filter(item_id__in=item_ids).exclude(status__in=["COMPLETED", "CANCELLED"]).select_related("item"):
        impacts.append(EngineeringImpact(change=change, impact_type="OPEN_WORK_ORDER", object_type="WorkOrder", object_id=str(order.pk), severity="CRITICAL", description=f"OP aberta para {order.item.code}", details={"order_number": order.number, "status": order.status}))
    for po in PlannedOrder.objects.filter(item_id__in=item_ids).select_related("item"):
        impacts.append(EngineeringImpact(change=change, impact_type="PLANNED_ORDER", object_type="PlannedOrder", object_id=str(po.pk), severity="MEDIUM", description=f"Ordem planejada para {po.item.code}", details={"quantity": str(po.quantity), "due_date": str(po.due_date)}))
    EngineeringImpact.objects.bulk_create(impacts, ignore_conflicts=True)
    summary={"affected_items": len(set(item_ids)), "where_used": sum(x.impact_type=="WHERE_USED" for x in impacts), "open_work_orders": sum(x.impact_type=="OPEN_WORK_ORDER" for x in impacts), "planned_orders": sum(x.impact_type=="PLANNED_ORDER" for x in impacts), "total": len(impacts)}
    change.impact_summary=summary; change.status=EngineeringChange.Status.ANALYSIS; change.save(update_fields=["impact_summary","status","updated_at"]); _event(change,"engineering_change.impact_analyzed",actor,summary); return change


@transaction.atomic
def submit_change(change, actor=None):
    change=EngineeringChange.objects.select_for_update().get(pk=change.pk)
    if change.status not in [EngineeringChange.Status.DRAFT, EngineeringChange.Status.ANALYSIS, EngineeringChange.Status.REJECTED]: raise ValidationError("A ECO não pode ser submetida neste estado.")
    if not change.items.exists(): raise ValidationError("Inclua ao menos um item afetado.")
    change.status=EngineeringChange.Status.APPROVAL; change.submitted_at=timezone.now(); change.save(update_fields=["status","submitted_at","updated_at"]); _event(change,"engineering_change.submitted",actor); return change


@transaction.atomic
def approve_change(change, actor=None, comment=""):
    change=EngineeringChange.objects.select_for_update().get(pk=change.pk)
    if change.status != EngineeringChange.Status.APPROVAL: raise ValidationError("A ECO não está em aprovação.")
    pending=change.approvals.filter(decision="PENDING").order_by("sequence").first()
    if pending:
        pending.decision="APPROVED"; pending.approver=actor; pending.decided_at=timezone.now(); pending.comment=comment; pending.save()
    if not change.approvals.filter(decision="PENDING").exists():
        change.status=EngineeringChange.Status.APPROVED; change.approved_by=actor; change.approved_at=timezone.now(); change.save(update_fields=["status","approved_by","approved_at","updated_at"]); _event(change,"engineering_change.approved",actor)
    return change


@transaction.atomic
def reject_change(change, actor=None, comment=""):
    change=EngineeringChange.objects.select_for_update().get(pk=change.pk)
    if change.status != EngineeringChange.Status.APPROVAL: raise ValidationError("A ECO não está em aprovação.")
    pending=change.approvals.filter(decision="PENDING").order_by("sequence").first()
    if pending:
        pending.decision="REJECTED"; pending.approver=actor; pending.decided_at=timezone.now(); pending.comment=comment; pending.save()
    change.status=EngineeringChange.Status.REJECTED; change.save(update_fields=["status","updated_at"]); _event(change,"engineering_change.rejected",actor,{"comment":comment}); return change


@transaction.atomic
def activate_change(change, actor=None):
    change=EngineeringChange.objects.select_for_update().get(pk=change.pk)
    if change.status not in [EngineeringChange.Status.APPROVED, EngineeringChange.Status.SCHEDULED]: raise ValidationError("Somente ECO aprovada ou programada pode ser efetivada.")
    today=timezone.localdate()
    if change.effectivity_type==EngineeringChange.EffectivityType.DATE and change.effective_date and change.effective_date>today:
        change.status=EngineeringChange.Status.SCHEDULED; change.save(update_fields=["status","updated_at"]); return change
    for rev in BOMRevision.objects.select_for_update().filter(change=change):
        BOMRevision.objects.filter(plant=rev.plant,parent=rev.parent,status=BOMRevision.Status.RELEASED).exclude(pk=rev.pk).update(status=BOMRevision.Status.OBSOLETE,effective_to=today)
        rev.status=BOMRevision.Status.RELEASED; rev.effective_from=change.effective_date or today; rev.save(update_fields=["status","effective_from","updated_at"])
        BOMLine.objects.filter(parent=rev.parent,is_active=True).update(is_active=False,effective_to=today)
        BOMLine.objects.bulk_create([BOMLine(parent=rev.parent,component=l.component,sequence=l.sequence,quantity_per=l.quantity_per,scrap_percent=l.scrap_percent,bom_type=BOMLine.BOMType.MANUFACTURING,effective_from=rev.effective_from,engineering_change=change.number,is_active=True) for l in rev.lines.select_related("component")])
    for item_id in change.items.values_list("affected_item_id",flat=True):
        PlanningChange.objects.get_or_create(plant=change.plant, item_id=item_id, change_type=PlanningChange.ChangeType.BOM, source_type="EngineeringChange", source_id=str(change.pk), idempotency_key=f"eco:{change.pk}:item:{item_id}", defaults={"payload": {"engineering_change": change.number}})
    change.status=EngineeringChange.Status.EFFECTIVE; change.activated_at=timezone.now(); change.save(update_fields=["status","activated_at","updated_at"]); _event(change,"engineering_change.activated",actor); return change
