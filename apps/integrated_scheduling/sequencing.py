from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from django.utils import timezone

from apps.production.models import WorkOrderOperation
from .models import ItemSchedulingProfile, SequenceSetupRule

ZERO = Decimal("0")


def profile_for_block(block, scenario):
    op = WorkOrderOperation.objects.select_related("work_order__item").get(pk=int(block.source_id))
    profile = ItemSchedulingProfile.objects.filter(plant=scenario.plant, item=op.work_order.item).select_related("family").first()
    return op, profile


def dispatch_key(block, scenario, now=None):
    """Menor chave sai primeiro. Implementa EDD, SPT, CR e prioridade comercial."""
    now = now or timezone.now()
    op, profile = profile_for_block(block, scenario)
    processing = Decimal(block.required_hours or ZERO)
    due_dt = timezone.make_aware(datetime.combine(op.work_order.due_date, datetime.max.time()))
    hours_to_due = Decimal(str((due_dt - now).total_seconds() / 3600))
    priority = Decimal(profile.commercial_priority if profile else 50)
    rule = scenario.dispatch_rule
    if rule == "SPT":
        return (processing, op.work_order.due_date, block.pk)
    if rule == "CR":
        cr = hours_to_due / processing if processing > 0 else Decimal("999999")
        return (cr, op.work_order.due_date, block.pk)
    if rule == "PRIORITY":
        return (-priority, op.work_order.due_date, processing, block.pk)
    if rule == "SETUP_MIN":
        family = profile.family.code if profile and profile.family_id else "~"
        campaign = profile.campaign_code if profile else ""
        return (campaign or family, family, op.work_order.due_date, block.pk)
    return (op.work_order.due_date, processing, block.pk)


def sequence_blocks(blocks, scenario):
    rows = sorted(blocks, key=lambda b: dispatch_key(b, scenario), reverse=scenario.scheduling_direction == "BACKWARD")
    if scenario.campaign_mode:
        # Agrupa campanhas/famílias mantendo o critério de despacho dentro de cada grupo.
        def campaign_key(b):
            _, profile = profile_for_block(b, scenario)
            campaign = (profile.campaign_code if profile else "") or (profile.family.code if profile and profile.family_id else "~")
            return (campaign, dispatch_key(b, scenario))
        rows = sorted(blocks, key=campaign_key, reverse=scenario.scheduling_direction == "BACKWARD")
    return rows


def family_for_block(block, scenario):
    _, profile = profile_for_block(block, scenario)
    return profile.family if profile and profile.family_id else None


def setup_hours(*, scenario, center, machine, from_family, to_family):
    if not scenario.minimize_setups or not to_family:
        return ZERO
    qs = SequenceSetupRule.objects.filter(
        plant=scenario.plant, work_center=center, to_family=to_family, is_active=True,
    )
    if from_family:
        qs = qs.filter(from_family=from_family)
    else:
        qs = qs.filter(from_family__isnull=True)
    # regra específica de máquina precede regra genérica do centro
    if machine:
        specific = qs.filter(machine=machine).first()
        if specific:
            return Decimal(specific.setup_hours)
    generic = qs.filter(machine__isnull=True).first()
    return Decimal(generic.setup_hours) if generic else ZERO


def adjacent_family(assigned, *, center, machine, direction):
    relevant = []
    for block in assigned:
        if machine and block.machine_id != machine.id:
            continue
        if machine is None and (block.machine_id is not None or block.work_center_id != center.id):
            continue
        relevant.append(block)
    if not relevant:
        return None
    if direction == "BACKWARD":
        neighbour = min(relevant, key=lambda b: b.simulated_start)
    else:
        neighbour = max(relevant, key=lambda b: b.simulated_end)
    return family_for_block(neighbour, neighbour.scenario)
