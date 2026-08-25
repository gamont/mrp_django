from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.masterdata.models import BOMLine, Item, Routing
from apps.costing.models import CostRollupRun, CostVersion, ItemCost, WorkCenterRate

D=Decimal

def _operation_cost(item, version):
    routing=(Routing.objects.filter(plant=version.plant,item=item,is_primary=True,is_active=True).prefetch_related("operations__work_center").first())
    parts={"setup":D("0"),"labor":D("0"),"machine":D("0"),"overhead":D("0")}
    if not routing: return parts
    rates={r.work_center_id:r for r in WorkCenterRate.objects.filter(cost_version=version)}
    for op in routing.operations.all():
        rate=rates.get(op.work_center_id)
        if not rate: continue
        parts["setup"] += op.setup_hours*rate.setup_rate
        parts["labor"] += op.run_hours_per_unit*rate.labor_rate
        parts["machine"] += op.run_hours_per_unit*rate.machine_rate
        parts["overhead"] += (op.setup_hours+op.run_hours_per_unit)*rate.overhead_rate
    return parts

@transaction.atomic
def run_rollup(cost_version: CostVersion):
    if cost_version.status == CostVersion.Status.ACTIVE:
        raise ValueError("Uma versão ativa não pode ser recalculada.")
    run=CostRollupRun.objects.create(cost_version=cost_version,status=CostRollupRun.Status.RUNNING,started_at=timezone.now())
    try:
        items=list(Item.objects.filter(is_active=True).order_by("-low_level_code","code"))
        cache={}
        for item in items:
            material=D("0"); detail=[]
            lines=BOMLine.objects.filter(parent=item,is_active=True).select_related("component")
            for line in lines:
                comp=cache.get(line.component_id)
                unit=(comp.total_cost if comp else line.component.standard_cost)
                qty=line.quantity_with_scrap()
                ext=unit*qty; material += ext
                detail.append({"component":line.component.code,"quantity":str(qty),"unit_cost":str(unit),"extended":str(ext)})
            if not detail and item.item_type in {Item.ItemType.PURCHASED,Item.ItemType.RAW,Item.ItemType.SUBCONTRACTED}:
                material=item.standard_cost
            ops=_operation_cost(item,cost_version)
            total=material+ops["setup"]+ops["labor"]+ops["machine"]+ops["overhead"]
            obj,_=ItemCost.objects.update_or_create(cost_version=cost_version,item=item,defaults={
                "material_cost":material,"setup_cost":ops["setup"],"labor_cost":ops["labor"],"machine_cost":ops["machine"],"overhead_cost":ops["overhead"],"total_cost":total,"level":item.low_level_code,"calculation_details":{"bom":detail}
            })
            cache[item.id]=obj
        run.status=CostRollupRun.Status.COMPLETED; run.finished_at=timezone.now(); run.items_calculated=len(items); run.save()
        cost_version.status=CostVersion.Status.CALCULATED; cost_version.calculated_at=timezone.now(); cost_version.save(update_fields=["status","calculated_at","updated_at"])
        return run
    except Exception as exc:
        run.status=CostRollupRun.Status.FAILED; run.finished_at=timezone.now(); run.error_message=str(exc); run.save(); raise
