from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.inventory.models import Reservation
from apps.production.models import WorkOrderMaterial
from .models import (
    IntegratedScheduleBlock, ProductionSchedulePublication, PublishedExecutionSlot,
    ReschedulingTrigger, ScheduleSolverRun,
)
from .execution import prepare_rescheduling_scenario, publish_solver_run


def freeze_baseline_into_scenario(trigger, scenario):
    """Remove frozen operations from solver decisions and reserve their occupied capacity."""
    pub = trigger.publication
    if not pub:
        return []
    frozen = list(pub.slots.filter(frozen=True).select_related('operation','work_center','machine'))
    ids = [s.operation_id for s in frozen]
    params = dict(scenario.parameters or {})
    params['frozen_operation_ids'] = ids
    params['base_publication_id'] = pub.pk
    params['frozen_until'] = pub.frozen_until.isoformat() if pub.frozen_until else None
    scenario.parameters = params
    scenario.save(update_fields=['parameters','updated_at'])
    for slot in frozen:
        IntegratedScheduleBlock.objects.update_or_create(
            scenario=scenario, source_type='FROZEN_EXECUTION_SLOT', source_id=str(slot.pk),
            defaults=dict(block_type=IntegratedScheduleBlock.BlockType.CAPACITY_LOSS,
                work_center=slot.work_center, machine=slot.machine, source_number=f'FROZEN-{slot.pk}',
                description=f'Frozen horizon · {slot.operation.work_order.number}/{slot.operation.sequence}',
                original_start=slot.planned_start, original_end=slot.planned_end,
                simulated_start=slot.planned_start, simulated_end=slot.planned_end,
                required_hours=Decimal(str((slot.planned_end-slot.planned_start).total_seconds()/3600)),
                lost_capacity_hours=Decimal(str((slot.planned_end-slot.planned_start).total_seconds()/3600)),
                details={'frozen': True, 'publication_id': pub.pk, 'operation_id': slot.operation_id},
                manually_locked=True,
            ))
    return ids


def build_recovery_comparison(trigger):
    pub, run = trigger.publication, trigger.resulting_solver_run
    if not pub or not run:
        return {'current': [], 'recovered': [], 'summary': {}}
    current = {s.operation_id:s for s in pub.slots.select_related('operation__work_order','machine','work_center')}
    recovered = {a.operation_id:a for a in run.assignments.select_related('operation__work_order','machine','work_center')}
    rows=[]; moved=late=machine_changes=0
    for op_id in sorted(set(current)|set(recovered)):
        c=current.get(op_id); r=recovered.get(op_id)
        if c and c.frozen:
            rows.append({'operation_id':op_id,'work_order':c.operation.work_order.number,'sequence':c.operation.sequence,'frozen':True,
                         'current_start':c.planned_start,'current_end':c.planned_end,'recovered_start':c.planned_start,'recovered_end':c.planned_end,
                         'current_machine':getattr(c.machine,'code',None),'recovered_machine':getattr(c.machine,'code',None),'delta_minutes':0})
            continue
        if not r: continue
        delta = int((r.start-c.planned_start).total_seconds()//60) if c else None
        if delta: moved += 1
        if r.tardiness_minutes: late += 1
        if c and c.machine_id != r.machine_id: machine_changes += 1
        rows.append({'operation_id':op_id,'work_order':r.operation.work_order.number,'sequence':r.operation.sequence,'frozen':False,
                     'current_start':c.planned_start if c else None,'current_end':c.planned_end if c else None,
                     'recovered_start':r.start,'recovered_end':r.end,
                     'current_machine':getattr(c.machine,'code',None) if c else None,'recovered_machine':getattr(r.machine,'code',None),
                     'delta_minutes':delta,'tardiness_minutes':r.tardiness_minutes})
    summary={'operations':len(rows),'moved_operations':moved,'late_operations':late,'machine_changes':machine_changes,
             'solver_status':run.status,'objective':str(run.objective_value) if run.objective_value is not None else None,
             'frozen_operations':sum(1 for x in rows if x['frozen'])}
    return {'rows':rows,'summary':summary}


def detect_material_shortages(publication, lookahead_hours=24):
    end=timezone.now()+timedelta(hours=lookahead_hours)
    slots=publication.slots.filter(planned_start__lte=end, actual_end__isnull=True).select_related('operation__work_order')
    shortages=[]
    seen=set()
    for slot in slots:
        wo=slot.operation.work_order
        if wo.pk in seen: continue
        seen.add(wo.pk)
        for m in WorkOrderMaterial.objects.filter(work_order=wo).select_related('item'):
            open_qty=m.required_quantity-m.issued_quantity
            reserved=(Reservation.objects.filter(demand_type='WORK_ORDER',demand_id=str(wo.pk),status=Reservation.Status.OPEN,requested_item=m.item)
                      .aggregate(q=Sum('requested_quantity'))['q'] or Decimal('0'))
            if reserved < open_qty:
                shortages.append({'work_order_id':wo.pk,'work_order':wo.number,'item_id':m.item_id,'item':m.item.code,
                                  'required_open':str(open_qty),'reserved':str(reserved),'shortage':str(open_qty-reserved),
                                  'slot_id':slot.pk})
    return shortages


@transaction.atomic
def publish_recovery(trigger, actor=None, notes=''):
    run=trigger.resulting_solver_run
    if not run or run.status not in {ScheduleSolverRun.Status.OPTIMAL, ScheduleSolverRun.Status.FEASIBLE}:
        raise ValueError('Plano recuperado ainda não possui solver factível.')
    old=trigger.publication
    pub=publish_solver_run(run=run, actor=actor, frozen_hours=0, notes=notes or f'Recovery trigger #{trigger.pk}')
    # Merge frozen baseline slots into the new publication because they were excluded from solver decisions.
    if old:
        for slot in old.slots.filter(frozen=True).select_related('operation','work_center','machine'):
            PublishedExecutionSlot.objects.get_or_create(publication=pub, operation=slot.operation, defaults={
                'work_center':slot.work_center,'machine':slot.machine,'planned_start':slot.planned_start,'planned_end':slot.planned_end,
                'frozen':True,'status':slot.status,'actual_start':slot.actual_start,'actual_end':slot.actual_end,
                'team_snapshot':slot.team_snapshot,'details':{**(slot.details or {}),'recovered_from_publication':old.pk},
            })
    trigger.status=ReschedulingTrigger.Status.PUBLISHED
    trigger.approved_at=timezone.now(); trigger.approved_by=actor
    trigger.save(update_fields=['status','approved_at','approved_by','updated_at'])
    return pub
