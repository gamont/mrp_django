from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.common.models import Plant
from apps.demand.models import MasterProductionSchedule
from apps.inventory.models import StockBalance
from apps.masterdata.models import BOMLine, ItemPlantPolicy, Routing, RoutingOperation, WorkCenterShift
from apps.production.models import WorkOrder
from apps.purchasing.models import PurchaseOrderLine

from .models import PlanningChange
from .net_change import enqueue_planning_change


def _key(instance, operation: str) -> str:
    stamp = getattr(instance, "updated_at", None) or getattr(instance, "created_at", None)
    stamp_text = stamp.isoformat() if stamp else "unknown"
    return f"planning-change:{instance._meta.label_lower}:{instance.pk}:{operation}:{stamp_text}"


def _enqueue_after_commit(*, plant, item, change_type, instance, operation, payload=None):
    key = _key(instance, operation)
    source_type = instance._meta.label.upper()
    source_id = instance.pk

    def callback():
        enqueue_planning_change(
            plant=plant,
            item=item,
            change_type=change_type,
            source_type=source_type,
            source_id=source_id,
            idempotency_key=key,
            payload=payload or {"operation": operation},
        )

    transaction.on_commit(callback)


@receiver(post_save, sender=MasterProductionSchedule, dispatch_uid="mrp_change_mps_save")
@receiver(post_delete, sender=MasterProductionSchedule, dispatch_uid="mrp_change_mps_delete")
def mps_changed(sender, instance, **kwargs):
    _enqueue_after_commit(
        plant=instance.plant,
        item=instance.item,
        change_type=PlanningChange.ChangeType.DEMAND,
        instance=instance,
        operation="DELETE" if kwargs.get("signal") is post_delete else "SAVE",
    )


@receiver(post_save, sender=StockBalance, dispatch_uid="mrp_change_stock_save")
def stock_changed(sender, instance, **kwargs):
    _enqueue_after_commit(
        plant=instance.location.warehouse.plant,
        item=instance.item,
        change_type=PlanningChange.ChangeType.STOCK,
        instance=instance,
        operation="SAVE",
        payload={
            "on_hand": str(instance.on_hand),
            "allocated": str(instance.allocated),
        },
    )


@receiver(post_save, sender=ItemPlantPolicy, dispatch_uid="mrp_change_policy_save")
@receiver(post_delete, sender=ItemPlantPolicy, dispatch_uid="mrp_change_policy_delete")
def policy_changed(sender, instance, **kwargs):
    _enqueue_after_commit(
        plant=instance.plant,
        item=instance.item,
        change_type=PlanningChange.ChangeType.POLICY,
        instance=instance,
        operation="DELETE" if kwargs.get("signal") is post_delete else "SAVE",
    )


@receiver(post_save, sender=BOMLine, dispatch_uid="mrp_change_bom_save")
@receiver(post_delete, sender=BOMLine, dispatch_uid="mrp_change_bom_delete")
def bom_changed(sender, instance, **kwargs):
    operation = "DELETE" if kwargs.get("signal") is post_delete else "SAVE"
    plants = list(Plant.objects.filter(is_active=True))
    for plant in plants:
        _enqueue_after_commit(
            plant=plant,
            item=instance.parent,
            change_type=PlanningChange.ChangeType.BOM,
            instance=instance,
            operation=f"{operation}:{plant.pk}",
            payload={"component_id": instance.component_id},
        )


@receiver(post_save, sender=PurchaseOrderLine, dispatch_uid="mrp_change_po_line_save")
@receiver(post_delete, sender=PurchaseOrderLine, dispatch_uid="mrp_change_po_line_delete")
def purchase_line_changed(sender, instance, **kwargs):
    _enqueue_after_commit(
        plant=instance.purchase_order.plant,
        item=instance.item,
        change_type=PlanningChange.ChangeType.SUPPLY,
        instance=instance,
        operation="DELETE" if kwargs.get("signal") is post_delete else "SAVE",
    )


@receiver(post_save, sender=WorkOrder, dispatch_uid="mrp_change_work_order_save")
@receiver(post_delete, sender=WorkOrder, dispatch_uid="mrp_change_work_order_delete")
def work_order_changed(sender, instance, **kwargs):
    _enqueue_after_commit(
        plant=instance.plant,
        item=instance.item,
        change_type=PlanningChange.ChangeType.SUPPLY,
        instance=instance,
        operation="DELETE" if kwargs.get("signal") is post_delete else "SAVE",
    )


@receiver(post_save, sender=Routing, dispatch_uid="mrp_change_routing_save")
@receiver(post_delete, sender=Routing, dispatch_uid="mrp_change_routing_delete")
def routing_changed(sender, instance, **kwargs):
    _enqueue_after_commit(
        plant=instance.plant,
        item=instance.item,
        change_type=PlanningChange.ChangeType.ROUTING,
        instance=instance,
        operation="DELETE" if kwargs.get("signal") is post_delete else "SAVE",
    )


@receiver(post_save, sender=RoutingOperation, dispatch_uid="mrp_change_routing_op_save")
@receiver(post_delete, sender=RoutingOperation, dispatch_uid="mrp_change_routing_op_delete")
def routing_operation_changed(sender, instance, **kwargs):
    _enqueue_after_commit(
        plant=instance.routing.plant,
        item=instance.routing.item,
        change_type=PlanningChange.ChangeType.ROUTING,
        instance=instance,
        operation="DELETE" if kwargs.get("signal") is post_delete else "SAVE",
    )


@receiver(post_save, sender=WorkCenterShift, dispatch_uid="mrp_change_shift_save")
@receiver(post_delete, sender=WorkCenterShift, dispatch_uid="mrp_change_shift_delete")
def shift_changed(sender, instance, **kwargs):
    _enqueue_after_commit(
        plant=instance.work_center.plant,
        item=None,
        change_type=PlanningChange.ChangeType.ROUTING,
        instance=instance,
        operation="DELETE" if kwargs.get("signal") is post_delete else "SAVE",
    )
