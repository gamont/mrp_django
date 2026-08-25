from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.costing.models import CostVersion, ItemCost, LotActualCost, SerialActualCost, WorkOrderCost
from apps.traceability.models import InventoryLot, LotBalance, SerialNumber, SerialComponent

ZERO = Decimal("0")


def _active_version(plant):
    return CostVersion.objects.filter(plant=plant, status=CostVersion.Status.ACTIVE).order_by("-effective_from").first()


@transaction.atomic
def calculate_lot_actual_cost(lot: InventoryLot):
    lot = InventoryLot.objects.select_for_update().get(pk=lot.pk)
    qty = lot.balances.aggregate(v=Sum("on_hand"))["v"] or ZERO
    version = _active_version(lot.plant)
    standard = ItemCost.objects.filter(cost_version=version, item=lot.item).first() if version else None
    purchase_cost = ZERO
    conversion_cost = ZERO
    details = {"source_type": lot.source_type, "source_id": lot.source_id}
    if lot.source_type.upper() in {"WORK_ORDER", "WO", "PRODUCTION"} and lot.source_id:
        wo_cost = WorkOrderCost.objects.filter(work_order__number=lot.source_id, cost_type=WorkOrderCost.CostType.ACTUAL).first()
        if wo_cost:
            conversion_cost = wo_cost.total_cost
            qty = wo_cost.quantity_basis or qty
            details["work_order_cost_id"] = wo_cost.pk
    elif standard:
        purchase_cost = qty * standard.total_cost
    total = purchase_cost + conversion_cost
    unit = (total / qty) if qty else (standard.total_cost if standard else ZERO)
    obj, _ = LotActualCost.objects.update_or_create(
        lot=lot,
        defaults={"cost_version": version, "quantity_basis": qty, "purchase_cost": purchase_cost,
                  "conversion_cost": conversion_cost, "total_cost": total, "unit_cost": unit,
                  "calculated_at": timezone.now(), "details": details},
    )
    return obj


@transaction.atomic
def calculate_serial_actual_cost(serial: SerialNumber, _seen=None):
    _seen = set(_seen or ())
    if serial.pk in _seen:
        raise ValueError("Ciclo detectado na genealogia serial.")
    _seen.add(serial.pk)
    lot_cost = ZERO
    if serial.lot_id:
        lc = calculate_lot_actual_cost(serial.lot)
        lot_cost = lc.unit_cost
    component_cost = ZERO
    components = SerialComponent.objects.filter(parent_serial=serial, removed_at__isnull=True).select_related("component_serial")
    component_details = []
    for rel in components:
        cc = calculate_serial_actual_cost(rel.component_serial, _seen=set(_seen))
        amount = cc.total_cost * rel.quantity
        component_cost += amount
        component_details.append({"serial": rel.component_serial.serial_number, "quantity": str(rel.quantity), "cost": str(amount)})
    total = lot_cost + component_cost
    obj, _ = SerialActualCost.objects.update_or_create(
        serial=serial,
        defaults={"lot_cost": lot_cost, "component_cost": component_cost, "conversion_cost": ZERO,
                  "total_cost": total, "calculated_at": timezone.now(), "details": {"components": component_details}},
    )
    return obj
