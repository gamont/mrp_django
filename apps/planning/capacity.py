from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.services import append_domain_event
from apps.masterdata.models import Item, Routing, RoutingOperation, WorkCenter, WorkCenterShift
from apps.production.models import WorkOrder

from .models import CapacityAllocation, CapacityScenario, PlannedOrder

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
HOURS_QUANTUM = Decimal("0.0001")


def h(value: Decimal) -> Decimal:
    return value.quantize(HOURS_QUANTUM)


def week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


class FiniteCapacityScheduler:
    def __init__(self, scenario: CapacityScenario):
        self.scenario = scenario
        self.used: dict[tuple[int, date], Decimal] = defaultdict(Decimal)
        self.available_cache: dict[tuple[int, date], Decimal] = {}
        self.allocations: list[CapacityAllocation] = []
        self.promised_dates: dict[tuple[str, str], date] = {}
        self.calendar = {
            row.date: (row.is_working_day, row.capacity_factor)
            for row in scenario.plant.calendar_days.all()
        }
        self.shifts: dict[tuple[int, int], list[WorkCenterShift]] = defaultdict(list)
        for shift in WorkCenterShift.objects.filter(
            work_center__plant=scenario.plant, is_active=True
        ).select_related("work_center"):
            self.shifts[(shift.work_center_id, shift.weekday)].append(shift)
        self.capacity_overrides = scenario.parameters.get("capacity_overrides", {}) or {}

    def _override(self, work_center: WorkCenter):
        return self.capacity_overrides.get(str(work_center.pk)) or self.capacity_overrides.get(
            work_center.code
        )

    def available_hours(self, work_center: WorkCenter, load_date: date) -> Decimal:
        cache_key = (work_center.pk, load_date)
        if cache_key in self.available_cache:
            return self.available_cache[cache_key]

        explicit = self.calendar.get(load_date)
        if explicit:
            is_working, factor = explicit
        else:
            is_working, factor = load_date.weekday() < 5, Decimal("1")
        if not is_working:
            self.available_cache[cache_key] = ZERO
            return ZERO

        day_shifts = self.shifts.get((work_center.pk, load_date.weekday()), [])
        if day_shifts:
            base = sum(
                (
                    shift.capacity_hours
                    * shift.efficiency_percent
                    / ONE_HUNDRED
                    for shift in day_shifts
                ),
                ZERO,
            )
        else:
            base = (
                work_center.capacity_hours_per_day
                * work_center.efficiency_percent
                / ONE_HUNDRED
            )

        override = self._override(work_center)
        if isinstance(override, (int, float, str, Decimal)):
            base *= Decimal(str(override))
        elif isinstance(override, dict):
            if override.get("hours_per_day") is not None:
                base = Decimal(str(override["hours_per_day"]))
            if override.get("efficiency_percent") is not None:
                base *= Decimal(str(override["efficiency_percent"])) / ONE_HUNDRED
            if override.get("factor") is not None:
                base *= Decimal(str(override["factor"]))

        result = h(base * factor)
        self.available_cache[cache_key] = result
        return result

    def next_working_date(self, work_center: WorkCenter, start: date) -> date:
        current = start
        for _ in range(730):
            if self.available_hours(work_center, current) > ZERO:
                return current
            current += timedelta(days=1)
        raise ValidationError(f"Não foi encontrada capacidade para {work_center.code} em 730 dias.")

    def _select_work_center(self, op: RoutingOperation, earliest: date) -> WorkCenter:
        candidates = [op.work_center]
        if op.alternate_work_center_id:
            candidates.append(op.alternate_work_center)

        def seven_day_room(center):
            total = ZERO
            current = earliest
            for _ in range(14):
                available = self.available_hours(center, current)
                total += max(available - self.used[(center.pk, current)], ZERO)
                current += timedelta(days=1)
            return total

        return max(candidates, key=seven_day_room)

    def schedule_item(
        self,
        *,
        item: Item,
        quantity: Decimal,
        release_date: date,
        due_date: date,
        source_type: str,
        source_id: str | int,
        is_existing_load: bool,
        routing: Routing | None = None,
    ) -> date:
        routing = routing or item.routings.filter(
            plant=self.scenario.plant,
            is_primary=True,
            is_active=True,
        ).order_by("-version").first()
        if not routing:
            raise ValidationError(f"O item {item.code} não possui roteiro primário ativo na planta.")

        operations = list(
            routing.operations.select_related("work_center", "alternate_work_center").order_by("sequence")
        )
        if not operations:
            raise ValidationError(f"O roteiro {routing} não possui operações.")

        cursor = release_date
        promised = release_date
        source_key = (source_type, str(source_id))

        for op in operations:
            work_center = self._select_work_center(op, cursor)
            cursor = self.next_working_date(work_center, cursor)
            required = h(op.setup_hours + op.teardown_hours + op.run_hours_per_unit * quantity)
            remaining = required
            load_date = cursor
            last_allocated_date = cursor

            for _ in range(730):
                available = self.available_hours(work_center, load_date)
                already_used = self.used[(work_center.pk, load_date)]
                room = max(available - already_used, ZERO)
                allocated = min(room, remaining)

                if allocated > ZERO:
                    self.used[(work_center.pk, load_date)] += allocated
                    self.allocations.append(
                        CapacityAllocation(
                            scenario=self.scenario,
                            work_center=work_center,
                            item=item,
                            source_type=source_type,
                            source_id=str(source_id),
                            operation_sequence=op.sequence,
                            load_date=load_date,
                            week_start=week_start(load_date),
                            required_hours=allocated,
                            available_hours=available,
                            allocated_hours=allocated,
                            overload_hours=allocated if load_date > due_date else ZERO,
                            is_existing_load=is_existing_load,
                        )
                    )
                    remaining -= allocated
                    last_allocated_date = load_date
                    if remaining <= ZERO:
                        break
                load_date += timedelta(days=1)
            else:
                raise ValidationError(
                    f"Não foi possível programar a operação {op.sequence} de {item.code} em 730 dias."
                )

            promised = max(promised, last_allocated_date)
            # Respeita a precedência do roteiro: a próxima operação começa no dia seguinte.
            cursor = last_allocated_date + timedelta(days=1)

        self.promised_dates[source_key] = promised
        return promised

    def bulk_save(self):
        CapacityAllocation.objects.bulk_create(self.allocations, batch_size=1000)


def _schedule_open_work_orders(scheduler: FiniteCapacityScheduler):
    orders = WorkOrder.objects.filter(
        plant=scheduler.scenario.plant,
        status__in=[WorkOrder.Status.RELEASED, WorkOrder.Status.IN_PROGRESS],
    ).select_related("item", "routing").order_by("due_date", "release_date", "number")
    for order in orders:
        open_quantity = order.quantity - order.completed_quantity
        if open_quantity <= ZERO:
            continue
        scheduler.schedule_item(
            item=order.item,
            quantity=open_quantity,
            release_date=max(order.release_date, timezone.localdate()),
            due_date=order.due_date,
            source_type="WORK_ORDER",
            source_id=order.pk,
            is_existing_load=True,
            routing=order.routing,
        )


def capacity_bottleneck_summary(scenario: CapacityScenario, threshold: Decimal = Decimal("90")):
    day_rows: dict[tuple[int, date], dict] = {}
    centers: dict[int, WorkCenter] = {}
    late_days: set[tuple[int, date]] = set()

    for row in scenario.allocations.select_related("work_center").all():
        key = (row.work_center_id, row.load_date)
        centers[row.work_center_id] = row.work_center
        day = day_rows.setdefault(
            key,
            {
                "available": row.available_hours,
                "allocated": ZERO,
                "week_start": row.week_start,
            },
        )
        day["available"] = max(day["available"], row.available_hours)
        day["allocated"] += row.allocated_hours
        if row.overload_hours > ZERO:
            late_days.add(key)

    weekly: dict[tuple[int, date], dict] = {}
    for (center_id, load_date), day in day_rows.items():
        key = (center_id, day["week_start"])
        bucket = weekly.setdefault(
            key,
            {
                "work_center_id": center_id,
                "work_center_code": centers[center_id].code,
                "work_center_name": centers[center_id].name,
                "week_start": day["week_start"].isoformat(),
                "available_hours": ZERO,
                "allocated_hours": ZERO,
                "late_days": 0,
            },
        )
        bucket["available_hours"] += day["available"]
        bucket["allocated_hours"] += day["allocated"]
        if (center_id, load_date) in late_days:
            bucket["late_days"] += 1

    result = []
    for bucket in weekly.values():
        available = bucket["available_hours"]
        utilization = (bucket["allocated_hours"] / available * ONE_HUNDRED) if available else ZERO
        bucket["available_hours"] = str(h(available))
        bucket["allocated_hours"] = str(h(bucket["allocated_hours"]))
        bucket["utilization_percent"] = str(h(utilization))
        bucket["is_bottleneck"] = utilization >= threshold or bucket["late_days"] > 0
        if bucket["is_bottleneck"]:
            result.append(bucket)

    return sorted(result, key=lambda x: (-Decimal(x["utilization_percent"]), x["week_start"]))


@transaction.atomic
def _execute_capacity_scenario_atomic(scenario: CapacityScenario) -> CapacityScenario:
    scenario = CapacityScenario.objects.select_for_update(of=("self",)).select_related(
        "plant", "planning_run", "item"
    ).get(pk=scenario.pk)
    scenario.status = CapacityScenario.Status.RUNNING
    scenario.started_at = timezone.now()
    scenario.completed_at = None
    scenario.error_message = ""
    scenario.save(
        update_fields=["status", "started_at", "completed_at", "error_message", "updated_at"]
    )

    try:
        scenario.allocations.all().delete()
        scheduler = FiniteCapacityScheduler(scenario)

        if scenario.parameters.get("include_open_orders", True):
            _schedule_open_work_orders(scheduler)

        target_promised = None
        if scenario.scenario_type == CapacityScenario.ScenarioType.CRP:
            if not scenario.planning_run_id:
                raise ValidationError("Cenário CRP exige uma execução MRP.")
            orders = scenario.planning_run.planned_orders.filter(
                order_type=PlannedOrder.OrderType.MAKE,
                status__in=[PlannedOrder.Status.PLANNED, PlannedOrder.Status.FIRM],
            ).select_related("item").order_by("due_date", "release_date", "item__code")
            for order in orders:
                target_promised = scheduler.schedule_item(
                    item=order.item,
                    quantity=order.quantity,
                    release_date=order.release_date,
                    due_date=order.due_date,
                    source_type="PLANNED_ORDER",
                    source_id=order.pk,
                    is_existing_load=False,
                )
        else:
            if not scenario.item_id or not scenario.requested_release_date or not scenario.requested_due_date:
                raise ValidationError("CTP/what-if exige item, quantidade, release e due date.")
            if scenario.quantity <= ZERO:
                raise ValidationError("A quantidade do cenário deve ser positiva.")
            target_promised = scheduler.schedule_item(
                item=scenario.item,
                quantity=scenario.quantity,
                release_date=scenario.requested_release_date,
                due_date=scenario.requested_due_date,
                source_type=scenario.scenario_type,
                source_id=scenario.pk,
                is_existing_load=False,
            )

        scheduler.bulk_save()
        bottlenecks = capacity_bottleneck_summary(scenario)
        total_hours = sum(
            (row.allocated_hours for row in scheduler.allocations if not row.is_existing_load), ZERO
        )
        existing_hours = sum(
            (row.allocated_hours for row in scheduler.allocations if row.is_existing_load), ZERO
        )

        if scenario.scenario_type == CapacityScenario.ScenarioType.CRP:
            late_sources = []
            due_by_id = {
                str(row.pk): row.due_date
                for row in scenario.planning_run.planned_orders.filter(
                    order_type=PlannedOrder.OrderType.MAKE,
                    status__in=[PlannedOrder.Status.PLANNED, PlannedOrder.Status.FIRM],
                )
            }
            for (source_type, source_id), promised in scheduler.promised_dates.items():
                if source_type == "PLANNED_ORDER" and promised > due_by_id.get(source_id, promised):
                    late_sources.append(
                        {
                            "planned_order_id": source_id,
                            "due_date": due_by_id[source_id].isoformat(),
                            "promised_date": promised.isoformat(),
                        }
                    )
            feasible = not late_sources
            promised_date = max(
                (
                    promised
                    for (source_type, _), promised in scheduler.promised_dates.items()
                    if source_type == "PLANNED_ORDER"
                ),
                default=None,
            )
        else:
            promised_date = target_promised
            feasible = promised_date <= scenario.requested_due_date
            late_sources = []

        scenario.promised_date = promised_date
        scenario.feasible = feasible
        scenario.summary = {
            "total_new_load_hours": str(h(total_hours)),
            "existing_load_hours": str(h(existing_hours)),
            "allocation_rows": len(scheduler.allocations),
            "bottleneck_count": len(bottlenecks),
            "bottlenecks": bottlenecks[:20],
            "late_sources": late_sources[:100],
        }
        scenario.status = CapacityScenario.Status.COMPLETED
        scenario.completed_at = timezone.now()
        scenario.save(
            update_fields=[
                "promised_date",
                "feasible",
                "summary",
                "status",
                "completed_at",
                "updated_at",
            ]
        )
        append_domain_event(
            idempotency_key=f"event:capacity-scenario:{scenario.pk}:{scenario.updated_at.isoformat()}",
            event_type="CAPACITY_SCENARIO_COMPLETED",
            aggregate_type="CAPACITY_SCENARIO",
            aggregate_id=scenario.pk,
            payload={
                "scenario_type": scenario.scenario_type,
                "feasible": scenario.feasible,
                "promised_date": scenario.promised_date.isoformat() if scenario.promised_date else None,
                "bottleneck_count": len(bottlenecks),
            },
        )
        return scenario
    except Exception as exc:
        scenario.status = CapacityScenario.Status.FAILED
        scenario.completed_at = timezone.now()
        scenario.error_message = str(exc)
        scenario.save(
            update_fields=["status", "completed_at", "error_message", "updated_at"]
        )
        raise


def execute_capacity_scenario(scenario: CapacityScenario) -> CapacityScenario:
    """Executa o cenário e persiste o estado FAILED fora da transação abortada."""

    scenario_id = scenario.pk
    try:
        return _execute_capacity_scenario_atomic(scenario)
    except Exception as exc:
        failed = CapacityScenario.objects.get(pk=scenario_id)
        failed.status = CapacityScenario.Status.FAILED
        failed.completed_at = timezone.now()
        failed.error_message = str(exc)
        failed.save(update_fields=["status", "completed_at", "error_message", "updated_at"])
        raise
