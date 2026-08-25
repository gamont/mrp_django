from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.demand.models import SalesOrderLine, SalesDeliveryLine
from .models import OTIFLineResult, ServiceLevelTarget, ServiceLevelPeriodSnapshot, ItemSchedulingProfile
from .commercial_confirmation import effective_customer_commitment_date


def _pct(n, d):
    return Decimal(str(round((n * 100 / d), 2))) if d else Decimal("0")


def _family_for(line):
    p = ItemSchedulingProfile.objects.filter(plant=line.sales_order.plant, item=line.item).select_related("family").first()
    return (p.family.code, p.family.name) if p and p.family_id else ("UNASSIGNED", "Sem família")


def _target(plant, scope, scope_key, at):
    return (ServiceLevelTarget.objects.filter(plant=plant, scope=scope, scope_key=scope_key, is_active=True, effective_from__lte=at)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=at)).order_by("-effective_from").first()
            or ServiceLevelTarget.objects.filter(plant=plant, scope="PLANT", scope_key="", is_active=True, effective_from__lte=at)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=at)).order_by("-effective_from").first())


def _delivery_count(line):
    return SalesDeliveryLine.objects.filter(sales_order_line=line).values("delivery_id").distinct().count()


def _overdue_backlog(lines, as_of):
    total = Decimal("0")
    for line in lines:
        open_qty = max(line.quantity - line.delivered_quantity, Decimal("0"))
        if open_qty and effective_customer_commitment_date(line) < as_of:
            total += open_qty
    return total


def _metrics(rows, target=None, as_of=None):
    rows = list(rows)
    as_of = as_of or timezone.localdate()
    n = len(rows)
    ordered = sum((r.ordered_quantity for r in rows), Decimal("0"))
    delivered = sum((r.delivered_quantity for r in rows), Decimal("0"))
    on = sum(1 for r in rows if r.on_time)
    inf = sum(1 for r in rows if r.in_full)
    otif = sum(1 for r in rows if r.otif)
    perfect = sum(1 for r in rows if r.otif and _delivery_count(r.sales_order_line) <= 1)
    causes = Counter((r.primary_cause or "UNKNOWN") for r in rows if not r.otif)
    late_days = sum(max(r.days_late, 0) for r in rows if not r.on_time)
    incomplete = sum((max(r.ordered_quantity-r.delivered_quantity, Decimal("0")) for r in rows), Decimal("0"))
    failure_cost = Decimal("0")
    if target:
        failure_cost = (Decimal(late_days) * target.late_day_cost) + (incomplete * target.incomplete_unit_cost)
    return {
        "lines": n,
        "orders": len({r.sales_order_line.sales_order_id for r in rows}),
        "ordered_quantity": ordered,
        "delivered_quantity": delivered,
        "on_time_pct": _pct(on, n),
        "in_full_pct": _pct(inf, n),
        "otif_pct": _pct(otif, n),
        "fill_rate_pct": _pct(delivered, ordered),
        # Proxy because document accuracy/damage-free/invoice accuracy are not yet modeled.
        "perfect_order_proxy_pct": _pct(perfect, n),
        "estimated_service_failure_cost": failure_cost,
        "cause_summary": [{"category": k, "count": v} for k, v in causes.most_common()],
    }


def analytics(rows, group_by="CUSTOMER", as_of=None):
    rows = list(rows)
    groups = defaultdict(list)
    labels = {}
    for r in rows:
        line = r.sales_order_line
        if group_by == "PLANT": key = line.sales_order.plant.code; label = str(line.sales_order.plant)
        elif group_by == "ITEM": key = line.item.code; label = getattr(line.item, "name", line.item.code)
        elif group_by == "FAMILY": key, label = _family_for(line)
        else: key = line.sales_order.customer_code; label = line.sales_order.customer_name
        groups[key].append(r); labels[key] = label
    out = []
    for key, vals in groups.items():
        plant = vals[0].sales_order_line.sales_order.plant
        target = _target(plant, group_by, key if group_by != "PLANT" else "", vals[0].reference_date)
        m = _metrics(vals, target, as_of)
        lines = [x.sales_order_line for x in vals]
        m.update(scope_key=key, scope_label=labels[key], target_otif_pct=(target.otif_target_pct if target else None),
                 target_met=bool(target and m["otif_pct"] >= target.otif_target_pct), overdue_backlog_quantity=_overdue_backlog(lines, as_of or timezone.localdate()))
        out.append(m)
    return sorted(out, key=lambda x: (x["otif_pct"], -x["lines"]))


@transaction.atomic
def build_monthly_snapshots(plant, year, month, reference="CUSTOMER_ACCEPTED"):
    import calendar
    start = date(year, month, 1); end = date(year, month, calendar.monthrange(year, month)[1])
    base = OTIFLineResult.objects.select_related("sales_order_line__sales_order", "sales_order_line__item").filter(
        sales_order_line__sales_order__plant=plant, reference=reference, reference_date__range=(start, end))
    created = []
    for scope in ["PLANT", "CUSTOMER", "FAMILY", "ITEM"]:
        for row in analytics(base, scope, end):
            obj, _ = ServiceLevelPeriodSnapshot.objects.update_or_create(
                plant=plant, reference=reference, period_start=start, period_end=end, scope=scope,
                scope_key=("" if scope == "PLANT" else row["scope_key"]),
                defaults={
                    "scope_label": row["scope_label"], "lines": row["lines"], "orders": row["orders"],
                    "ordered_quantity": row["ordered_quantity"], "delivered_quantity": row["delivered_quantity"],
                    "overdue_backlog_quantity": row["overdue_backlog_quantity"], "on_time_pct": row["on_time_pct"],
                    "in_full_pct": row["in_full_pct"], "otif_pct": row["otif_pct"], "fill_rate_pct": row["fill_rate_pct"],
                    "perfect_order_proxy_pct": row["perfect_order_proxy_pct"],
                    "estimated_service_failure_cost": row["estimated_service_failure_cost"],
                    "target_otif_pct": row["target_otif_pct"], "target_met": row["target_met"],
                    "cause_summary": row["cause_summary"], "calculated_at": timezone.now(),
                    "details": {"perfect_order_is_proxy": True},
                })
            created.append(obj)
    return created
