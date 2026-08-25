from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from apps.shopfloor.models import DowntimeEvent, DowntimeReason
from .models import LaborUnavailability, ReschedulingTrigger, ProductionSchedulePublication
from .execution import create_rescheduling_trigger
from .tasks import auto_process_rescheduling_trigger_task


def _dispatch(trigger):
    if trigger.auto_reschedule:
        try: auto_process_rescheduling_trigger_task.delay(trigger.pk)
        except Exception: pass

@receiver(post_save, sender=DowntimeEvent)
def downtime_to_reschedule(sender, instance, created, **kwargs):
    if not created or instance.ended_at or instance.reason.category != DowntimeReason.Category.UNPLANNED: return
    plant=instance.machine.plant
    pub=ProductionSchedulePublication.objects.filter(plant=plant,status='PUBLISHED').first()
    if not pub or not pub.slots.filter(machine=instance.machine,planned_end__gte=instance.started_at).exists(): return
    tr=create_rescheduling_trigger(plant=plant,publication=pub,trigger_type=ReschedulingTrigger.TriggerType.MACHINE_BREAKDOWN,
        affected_from=instance.started_at,source_type='DowntimeEvent',source_id=instance.pk,
        idempotency_key=f'downtime:{instance.pk}:reschedule',payload={'machine_id':instance.machine_id,'reason':instance.reason.code})
    _dispatch(tr)

@receiver(post_save, sender=LaborUnavailability)
def absence_to_reschedule(sender, instance, created, **kwargs):
    if not created: return
    plant=instance.labor_resource.plant
    pub=ProductionSchedulePublication.objects.filter(plant=plant,status='PUBLISHED').first()
    if not pub: return
    token=str(instance.labor_resource_id)
    affected=False
    for slot in pub.slots.filter(planned_end__gt=instance.start,planned_start__lt=instance.end):
        if any(str(x.get('labor_resource_id'))==token for x in (slot.team_snapshot or [])):
            affected=True; break
    if not affected: return
    tr=create_rescheduling_trigger(plant=plant,publication=pub,trigger_type=ReschedulingTrigger.TriggerType.LABOR_ABSENCE,
        affected_from=instance.start,source_type='LaborUnavailability',source_id=instance.pk,
        idempotency_key=f'labor-unavailability:{instance.pk}:reschedule',payload={'labor_resource_id':instance.labor_resource_id,'end':instance.end.isoformat()})
    _dispatch(tr)
