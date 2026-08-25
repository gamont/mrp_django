from apps.common.models import Plant


def ui_context(request):
    selected_id = request.session.get("ui_plant_id") if hasattr(request, "session") else None
    plants = Plant.objects.filter(is_active=True).order_by("code")
    selected = plants.filter(pk=selected_id).first() if selected_id else plants.first()
    return {
        "ui_plants": plants,
        "ui_selected_plant": selected,
        "mrp_version": "0.5.2",
    }
