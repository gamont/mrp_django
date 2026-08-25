from __future__ import annotations

from collections import defaultdict, deque
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Iterable

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.demand.models import Forecast, MasterProductionSchedule, SalesOrder, SalesOrderLine
from apps.inventory.models import StockBalance
from apps.masterdata.models import BOMLine, Item, ItemPlantPolicy
from apps.production.models import WorkOrder
from apps.purchasing.models import PurchaseOrder, PurchaseOrderLine
from .models import DemandPeggingAllocation, PeggingRecord, PlannedOrder, PlanningBucket, PlanningMessage, PlanningRun

ZERO = Decimal("0")
ONE = Decimal("1")
QTY_QUANTUM = Decimal("0.0001")


class MRPDataError(Exception):
    pass


def q(value: Decimal) -> Decimal:
    return value.quantize(QTY_QUANTUM)


def _ceil_multiple(value: Decimal, multiple: Decimal) -> Decimal:
    if multiple <= 0:
        return value
    units = (value / multiple).to_integral_value(rounding=ROUND_CEILING)
    return units * multiple


def lot_size(requirement: Decimal, policy: ItemPlantPolicy | None) -> Decimal:
    if requirement <= 0:
        return ZERO
    if policy is None:
        return q(requirement)

    rule = policy.lot_sizing_rule
    if rule == ItemPlantPolicy.LotSizingRule.FIXED:
        return q(_ceil_multiple(requirement, policy.fixed_order_quantity))
    if rule == ItemPlantPolicy.LotSizingRule.MULTIPLE:
        return q(_ceil_multiple(requirement, policy.order_multiple))
    if rule == ItemPlantPolicy.LotSizingRule.MINIMUM:
        return q(max(requirement, policy.minimum_order_quantity))
    return q(requirement)


def _default_source(item: Item) -> str:
    if item.item_type in {
        Item.ItemType.PURCHASED,
        Item.ItemType.RAW,
        Item.ItemType.SUBCONTRACTED,
    }:
        return ItemPlantPolicy.SourceType.BUY
    return ItemPlantPolicy.SourceType.MAKE


def _is_effective(line: BOMLine, on_date: date) -> bool:
    if not line.is_active:
        return False
    if line.effective_from and on_date < line.effective_from:
        return False
    if line.effective_to and on_date > line.effective_to:
        return False
    return True


def _offset_workdays(target: date, days: int, calendar: dict[date, bool]) -> date:
    current = target
    remaining = days
    while remaining > 0:
        current -= timedelta(days=1)
        is_working = calendar.get(current, current.weekday() < 5)
        if is_working:
            remaining -= 1
    return current


def recalculate_low_level_codes(lines: Iterable[BOMLine]) -> dict[int, int]:
    graph: dict[int, set[int]] = defaultdict(set)
    indegree: dict[int, int] = defaultdict(int)
    item_ids: set[int] = set(Item.objects.filter(is_active=True).values_list("id", flat=True))

    for line in lines:
        if line.parent_id == line.component_id:
            raise MRPDataError(f"Ciclo direto na estrutura do item {line.parent_id}.")
        if line.component_id not in graph[line.parent_id]:
            graph[line.parent_id].add(line.component_id)
            indegree[line.component_id] += 1
        indegree.setdefault(line.parent_id, indegree.get(line.parent_id, 0))
        item_ids.update([line.parent_id, line.component_id])

    queue = deque(sorted(item_id for item_id in item_ids if indegree.get(item_id, 0) == 0))
    levels = {item_id: 0 for item_id in item_ids}
    processed = 0

    while queue:
        parent = queue.popleft()
        processed += 1
        for child in graph.get(parent, set()):
            levels[child] = max(levels.get(child, 0), levels[parent] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if processed != len(item_ids):
        raise MRPDataError("Foi detectado ciclo na lista de materiais (BOM).")

    items = list(Item.objects.filter(id__in=levels.keys()))
    for item in items:
        item.low_level_code = levels[item.id]
    Item.objects.bulk_update(items, ["low_level_code"])
    return levels


def execute_planning_run(run: PlanningRun) -> PlanningRun:
    run.status = PlanningRun.Status.RUNNING
    run.started_at = timezone.now()
    run.completed_at = None
    run.error_message = ""
    run.save(update_fields=["status", "started_at", "completed_at", "error_message", "updated_at"])

    try:
        with transaction.atomic():
            run.buckets.all().delete()
            run.planned_orders.all().delete()
            run.pegging_records.all().delete()
            run.messages.all().delete()

            bom_lines = list(
                BOMLine.objects.filter(is_active=True)
                .select_related("parent", "component")
                .order_by("parent_id", "sequence")
            )
            recalculate_low_level_codes(bom_lines)

            item_queryset = Item.objects.filter(is_active=True)
            scope_item_ids = run.parameters.get("scope_item_ids") or []
            if scope_item_ids:
                item_queryset = item_queryset.filter(id__in=scope_item_ids)
            items = list(item_queryset.order_by("low_level_code", "code"))
            policies = {
                p.item_id: p
                for p in ItemPlantPolicy.objects.filter(plant=run.plant).select_related("item")
            }
            bom_by_parent: dict[int, list[BOMLine]] = defaultdict(list)
            for line in bom_lines:
                bom_by_parent[line.parent_id].append(line)

            calendar = {
                row.date: row.is_working_day
                for row in run.plant.calendar_days.filter(
                    date__gte=run.horizon_start - timedelta(days=370),
                    date__lte=run.horizon_end,
                )
            }

            demands: dict[int, dict[date, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
            demand_sources: dict[int, dict[date, list[dict]]] = defaultdict(lambda: defaultdict(list))
            top_level_sources: dict[tuple[int, date], int] = {}

            # 0.8.3: what-if MRP can inject a revision snapshot without creating
            # temporary MasterProductionSchedule rows in the shared database.
            inline_mps = run.parameters.get("inline_mps_demands") or []
            if inline_mps:
                for src in inline_mps:
                    due = date.fromisoformat(src["due_date"]) if isinstance(src.get("due_date"), str) else src["due_date"]
                    if not (run.horizon_start <= due <= run.horizon_end):
                        continue
                    item_id = int(src["item_id"]); qty = q(Decimal(str(src.get("quantity") or 0)))
                    if qty <= ZERO:
                        continue
                    source_id = src.get("source_id")
                    demands[item_id][due] += qty
                    demand_sources[item_id][due].append({
                        "source_type": DemandPeggingAllocation.SourceType.MPS,
                        "source_id": source_id, "sales_order_line_id": None,
                        "quantity": qty, "top_level_item_id": item_id,
                        "source_model": src.get("source_model", "MPSRevisionLine"),
                    })
                    top_level_sources[(item_id, due)] = item_id
            else:
                mps_rows = MasterProductionSchedule.objects.filter(
                    plant=run.plant,
                    due_date__range=(run.horizon_start, run.horizon_end),
                ).exclude(status=MasterProductionSchedule.Status.CANCELLED)
                source_filter = run.parameters.get("mps_source_filter")
                if source_filter:
                    mps_rows = mps_rows.filter(source=source_filter)
                for row in mps_rows:
                    demands[row.item_id][row.due_date] += row.quantity
                    demand_sources[row.item_id][row.due_date].append({"source_type": DemandPeggingAllocation.SourceType.MPS, "source_id": row.id, "sales_order_line_id": None, "quantity": q(row.quantity), "top_level_item_id": row.item_id})
                    top_level_sources[(row.item_id, row.due_date)] = row.item_id

            if run.parameters.get("include_sales_orders", False):
                lines = SalesOrderLine.objects.filter(
                    sales_order__plant=run.plant,
                    sales_order__status__in=[SalesOrder.Status.CONFIRMED, SalesOrder.Status.PARTIAL],
                    requested_date__lte=run.horizon_end,
                ).annotate(open_qty=F("quantity") - F("delivered_quantity"))
                from apps.integrated_scheduling.commercial_confirmation import effective_customer_commitment_date
                for line in lines:
                    demand_date = effective_customer_commitment_date(line)
                    if line.open_qty > 0 and run.horizon_start <= demand_date <= run.horizon_end:
                        demands[line.item_id][demand_date] += line.open_qty
                        demand_sources[line.item_id][demand_date].append({"source_type": DemandPeggingAllocation.SourceType.SALES_ORDER_LINE, "source_id": line.id, "sales_order_line_id": line.id, "quantity": q(line.open_qty), "top_level_item_id": line.item_id, "contract_requested_date": line.requested_date.isoformat(), "effective_customer_commitment_date": demand_date.isoformat()})
                        top_level_sources[(line.item_id, demand_date)] = line.item_id

            if run.parameters.get("include_forecasts", False):
                forecasts = Forecast.objects.filter(
                    plant=run.plant,
                    status=Forecast.Status.APPROVED,
                    period_start__range=(run.horizon_start, run.horizon_end),
                )
                for row in forecasts:
                    demands[row.item_id][row.period_start] += row.quantity
                    demand_sources[row.item_id][row.period_start].append({"source_type": DemandPeggingAllocation.SourceType.FORECAST, "source_id": row.id, "sales_order_line_id": None, "quantity": q(row.quantity), "top_level_item_id": row.item_id})
                    top_level_sources[(row.item_id, row.period_start)] = row.item_id

            opening_stock = defaultdict(Decimal)
            stock_rows = (
                StockBalance.objects.filter(location__warehouse__plant=run.plant)
                .values("item_id")
                .annotate(total_on_hand=Sum("on_hand"), total_allocated=Sum("allocated"))
            )
            for row in stock_rows:
                opening_stock[row["item_id"]] = (row["total_on_hand"] or ZERO) - (
                    row["total_allocated"] or ZERO
                )

            scheduled: dict[int, dict[date, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
            po_lines = PurchaseOrderLine.objects.filter(
                purchase_order__plant=run.plant,
                purchase_order__status__in=[PurchaseOrder.Status.RELEASED, PurchaseOrder.Status.PARTIAL],
                expected_date__range=(run.horizon_start, run.horizon_end),
            ).annotate(open_qty=F("quantity") - F("received_quantity"))
            for line in po_lines:
                if line.open_qty > 0:
                    scheduled[line.item_id][line.expected_date] += line.open_qty

            work_orders = WorkOrder.objects.filter(
                plant=run.plant,
                status__in=[WorkOrder.Status.RELEASED, WorkOrder.Status.IN_PROGRESS],
                due_date__range=(run.horizon_start, run.horizon_end),
            ).annotate(open_qty=F("quantity") - F("completed_quantity"))
            for order in work_orders:
                if order.open_qty > 0:
                    scheduled[order.item_id][order.due_date] += order.open_qty

            for item in items:
                policy = policies.get(item.id)
                source_type = policy.source_type if policy else _default_source(item)
                lead_time = policy.lead_time_days if policy else 0
                safety_stock = policy.safety_stock if policy else ZERO
                yield_percent = policy.yield_percent if policy else Decimal("100")

                event_dates = sorted(set(demands[item.id].keys()) | set(scheduled[item.id].keys()))
                if not event_dates:
                    continue

                projected = opening_stock[item.id]
                for bucket_date in event_dates:
                    gross = q(demands[item.id][bucket_date])
                    receipt = q(scheduled[item.id][bucket_date])
                    projected = projected + receipt - gross
                    net = ZERO
                    planned_receipt = ZERO

                    if projected < safety_stock:
                        net = q(safety_stock - projected)
                        gross_order_qty = net * Decimal("100") / yield_percent
                        planned_receipt = lot_size(gross_order_qty, policy)
                        projected += planned_receipt
                        release_date = _offset_workdays(bucket_date, lead_time, calendar)
                        order_type = (
                            PlannedOrder.OrderType.MAKE
                            if source_type == ItemPlantPolicy.SourceType.MAKE
                            else PlannedOrder.OrderType.PURCHASE
                        )
                        planned_order = PlannedOrder.objects.create(
                            planning_run=run,
                            item=item,
                            order_type=order_type,
                            quantity=planned_receipt,
                            release_date=release_date,
                            due_date=bucket_date,
                        )

                        # Persist source-aware demand pegging. The shortage is attributed deterministically
                        # to demand sources in priority order; this allocation is then propagated through BOM explosion.
                        source_priority = {
                            DemandPeggingAllocation.SourceType.SALES_ORDER_LINE: 0,
                            DemandPeggingAllocation.SourceType.MPS: 1,
                            DemandPeggingAllocation.SourceType.FORECAST: 2,
                        }
                        remaining_to_allocate = q(min(net, planned_receipt))
                        allocated_sources = []
                        for src in sorted(demand_sources[item.id][bucket_date], key=lambda x: (source_priority.get(x["source_type"], 9), x.get("source_id") or 0)):
                            if remaining_to_allocate <= ZERO:
                                break
                            alloc_qty = q(min(Decimal(src["quantity"]), remaining_to_allocate))
                            if alloc_qty <= ZERO:
                                continue
                            DemandPeggingAllocation.objects.create(
                                planned_order=planned_order, source_type=src["source_type"],
                                sales_order_line_id=src.get("sales_order_line_id"), source_id=src.get("source_id"),
                                required_date=bucket_date, quantity=alloc_qty, top_level_item_id=src.get("top_level_item_id"),
                                details={"allocation_policy": "SALES_ORDER_MPS_FORECAST", "mrp_run_id": run.id},
                            )
                            allocated_sources.append({**src, "quantity": alloc_qty})
                            remaining_to_allocate = q(remaining_to_allocate - alloc_qty)
                        if remaining_to_allocate > ZERO:
                            DemandPeggingAllocation.objects.create(
                                planned_order=planned_order, source_type=DemandPeggingAllocation.SourceType.SAFETY_STOCK,
                                required_date=bucket_date, quantity=remaining_to_allocate, top_level_item=item,
                                details={"allocation_policy": "RESIDUAL_SAFETY_STOCK", "mrp_run_id": run.id},
                            )

                        if release_date < run.horizon_start:
                            PlanningMessage.objects.create(
                                planning_run=run,
                                item=item,
                                planned_order=planned_order,
                                message_type=PlanningMessage.MessageType.PAST_DUE,
                                severity=PlanningMessage.Severity.WARNING,
                                action_date=release_date,
                                message=f"A liberação calculada para {item.code} está antes do início do horizonte.",
                            )
                        else:
                            PlanningMessage.objects.create(
                                planning_run=run,
                                item=item,
                                planned_order=planned_order,
                                message_type=PlanningMessage.MessageType.RELEASE,
                                severity=PlanningMessage.Severity.INFO,
                                action_date=release_date,
                                message=f"Liberar {planned_receipt} {item.uom} de {item.code}.",
                            )

                        if order_type == PlannedOrder.OrderType.MAKE:
                            effective_lines = [
                                line
                                for line in bom_by_parent.get(item.id, [])
                                if _is_effective(line, release_date)
                            ]
                            for line in effective_lines:
                                component_qty = q(planned_receipt * line.quantity_with_scrap())
                                demands[line.component_id][release_date] += component_qty
                                top_item_id = top_level_sources.get((item.id, bucket_date), item.id)
                                top_level_sources[(line.component_id, release_date)] = top_item_id
                                # Propagate exact commercial/MPS/forecast source through the BOM.
                                for src in allocated_sources:
                                    propagated = q(Decimal(src["quantity"]) * line.quantity_with_scrap())
                                    if propagated > ZERO:
                                        demand_sources[line.component_id][release_date].append({**src, "quantity": propagated})
                                PeggingRecord.objects.create(
                                    planning_run=run,
                                    component_item=line.component,
                                    parent_item=item,
                                    parent_planned_order=planned_order,
                                    top_level_item_id=top_item_id,
                                    requirement_date=release_date,
                                    quantity=component_qty,
                                )

                    PlanningBucket.objects.create(
                        planning_run=run,
                        item=item,
                        bucket_date=bucket_date,
                        gross_requirements=gross,
                        scheduled_receipts=receipt,
                        projected_available=q(projected),
                        net_requirements=net,
                        planned_order_receipts=planned_receipt,
                    )

            release_totals = defaultdict(Decimal)
            for row in run.planned_orders.values("item_id", "release_date").annotate(total=Sum("quantity")):
                release_totals[(row["item_id"], row["release_date"])] = row["total"]

            for (item_id, release_date), total in release_totals.items():
                bucket, _ = PlanningBucket.objects.get_or_create(
                    planning_run=run,
                    item_id=item_id,
                    bucket_date=release_date,
                    defaults={"projected_available": opening_stock[item_id]},
                )
                bucket.planned_order_releases = total
                bucket.save(update_fields=["planned_order_releases", "updated_at"])

            _generate_reschedule_messages(run, policies)

            run.status = PlanningRun.Status.COMPLETED
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at", "updated_at"])
        return run
    except Exception as exc:
        run.refresh_from_db()
        run.status = PlanningRun.Status.FAILED
        run.completed_at = timezone.now()
        run.error_message = str(exc)
        run.save(update_fields=["status", "completed_at", "error_message", "updated_at"])
        raise


@transaction.atomic
def convert_planned_order(order: PlannedOrder):
    if order.status not in {PlannedOrder.Status.PLANNED, PlannedOrder.Status.FIRM}:
        raise MRPDataError("A ordem planejada já foi convertida ou cancelada.")

    if order.order_type == PlannedOrder.OrderType.MAKE:
        number = f"OP-{order.planning_run_id}-{order.id}"
        document = WorkOrder.objects.create(
            number=number,
            plant=order.planning_run.plant,
            item=order.item,
            quantity=order.quantity,
            release_date=order.release_date,
            due_date=order.due_date,
            planning_run_id=order.planning_run_id,
            planned_order_id=order.id,
        )
        document_type = "WORK_ORDER"
    else:
        supplier_link = order.item.suppliers.filter(
            plant=order.planning_run.plant, is_primary=True
        ).select_related("supplier").first()
        if not supplier_link:
            raise MRPDataError(f"O item {order.item.code} não possui fornecedor principal.")
        number = f"OC-{order.planning_run_id}-{order.id}"
        po = PurchaseOrder.objects.create(
            number=number,
            plant=order.planning_run.plant,
            supplier=supplier_link.supplier,
            order_date=timezone.localdate(),
            expected_date=order.due_date,
            status=PurchaseOrder.Status.DRAFT,
            planning_run_id=order.planning_run_id,
            planned_order_id=order.id,
        )
        PurchaseOrderLine.objects.create(
            purchase_order=po,
            line_number=10,
            item=order.item,
            quantity=order.quantity,
            unit_price=supplier_link.unit_price,
            expected_date=order.due_date,
        )
        document = po
        document_type = "PURCHASE_ORDER"

    order.status = PlannedOrder.Status.CONVERTED
    order.converted_document_type = document_type
    order.converted_document_id = str(document.id)
    order.save(
        update_fields=[
            "status",
            "converted_document_type",
            "converted_document_id",
            "updated_at",
        ]
    )
    return document


def _generate_reschedule_messages(run: PlanningRun, policies: dict[int, ItemPlantPolicy]) -> None:
    """Gera sugestões heurísticas de antecipação/postergação para ordens abertas.

    A regra preserva as ordens existentes como recebimentos programados e só
    sugere mudança quando: (a) o MRP criou uma nova necessidade anterior ao
    recebimento, ou (b) o recebimento pode ser postergado sem violar o estoque
    de segurança na data atual.
    """

    sources = []
    po_lines = PurchaseOrderLine.objects.filter(
        purchase_order__plant=run.plant,
        purchase_order__status__in=[PurchaseOrder.Status.RELEASED, PurchaseOrder.Status.PARTIAL],
        expected_date__range=(run.horizon_start, run.horizon_end),
    ).annotate(open_qty=F("quantity") - F("received_quantity"))
    for line in po_lines:
        if line.open_qty > ZERO:
            sources.append(
                {
                    "item_id": line.item_id,
                    "date": line.expected_date,
                    "quantity": line.open_qty,
                    "type": "PURCHASE_ORDER_LINE",
                    "id": str(line.pk),
                    "label": f"OC {line.purchase_order.number} linha {line.line_number}",
                }
            )

    work_orders = WorkOrder.objects.filter(
        plant=run.plant,
        status__in=[WorkOrder.Status.RELEASED, WorkOrder.Status.IN_PROGRESS],
        due_date__range=(run.horizon_start, run.horizon_end),
    ).annotate(open_qty=F("quantity") - F("completed_quantity"))
    for order in work_orders:
        if order.open_qty > ZERO:
            sources.append(
                {
                    "item_id": order.item_id,
                    "date": order.due_date,
                    "quantity": order.open_qty,
                    "type": "WORK_ORDER",
                    "id": str(order.pk),
                    "label": f"OP {order.number}",
                }
            )

    for source in sources:
        earlier_shortage = run.planned_orders.filter(
            item_id=source["item_id"],
            due_date__lt=source["date"],
            status__in=[PlannedOrder.Status.PLANNED, PlannedOrder.Status.FIRM],
        ).order_by("due_date").first()
        if earlier_shortage:
            PlanningMessage.objects.create(
                planning_run=run,
                item_id=source["item_id"],
                message_type=PlanningMessage.MessageType.RESCHEDULE_IN,
                severity=PlanningMessage.Severity.WARNING,
                action_date=source["date"],
                suggested_date=earlier_shortage.due_date,
                reference_type=source["type"],
                reference_id=source["id"],
                message=(
                    f"Antecipar {source['label']} de {source['date']} para "
                    f"{earlier_shortage.due_date}; há necessidade anterior não atendida."
                ),
            )
            continue

        bucket = run.buckets.filter(
            item_id=source["item_id"], bucket_date=source["date"]
        ).first()
        policy = policies.get(source["item_id"])
        safety_stock = policy.safety_stock if policy else ZERO
        if not bucket or bucket.projected_available - source["quantity"] < safety_stock:
            continue

        next_demand = run.buckets.filter(
            item_id=source["item_id"],
            bucket_date__gt=source["date"],
            gross_requirements__gt=ZERO,
        ).order_by("bucket_date").first()
        if next_demand:
            PlanningMessage.objects.create(
                planning_run=run,
                item_id=source["item_id"],
                message_type=PlanningMessage.MessageType.RESCHEDULE_OUT,
                severity=PlanningMessage.Severity.INFO,
                action_date=source["date"],
                suggested_date=next_demand.bucket_date,
                reference_type=source["type"],
                reference_id=source["id"],
                message=(
                    f"Postergar {source['label']} de {source['date']} para "
                    f"{next_demand.bucket_date}; o estoque projetado permanece acima da segurança."
                ),
            )
