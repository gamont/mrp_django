from datetime import time, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.common.models import Plant
from apps.demand.models import MasterProductionSchedule
from apps.inventory.models import Location, StockBalance, Warehouse
from apps.masterdata.models import (
    BOMLine,
    Item,
    ItemPlantPolicy,
    ItemSubstitute,
    ItemSupplier,
    Routing,
    RoutingOperation,
    Supplier,
    WorkCenter,
    WorkCenterShift,
)


class Command(BaseCommand):
    help = "Cria dados de demonstração para uma fábrica de faróis automotivos."

    def handle(self, *args, **options):
        today = timezone.localdate()
        plant, _ = Plant.objects.get_or_create(code="SP01", defaults={"name": "Fábrica São Paulo"})
        warehouse, _ = Warehouse.objects.get_or_create(
            plant=plant, code="MP", defaults={"name": "Matéria-prima"}
        )
        location, _ = Location.objects.get_or_create(
            warehouse=warehouse, code="A-01", defaults={"description": "Posição principal"}
        )
        fg_warehouse, _ = Warehouse.objects.get_or_create(
            plant=plant, code="PA", defaults={"name": "Produto acabado"}
        )
        Location.objects.get_or_create(
            warehouse=fg_warehouse, code="PA-01", defaults={"description": "Recebimento da produção"}
        )

        item_data = [
            ("FAROL-H7", "Farol automotivo H7", Item.ItemType.FINISHED, "MAKE", 2),
            ("CONJ-OPTICO", "Conjunto óptico", Item.ItemType.ASSEMBLY, "MAKE", 2),
            ("CARCACA", "Carcaça plástica", Item.ItemType.PURCHASED, "BUY", 7),
            ("REFLETOR", "Refletor aluminizado", Item.ItemType.PURCHASED, "BUY", 10),
            ("LENTE", "Lente de policarbonato", Item.ItemType.PURCHASED, "BUY", 8),
            ("CHICOTE", "Chicote elétrico", Item.ItemType.PURCHASED, "BUY", 5),
            ("LAMPADA-H7", "Lâmpada H7", Item.ItemType.PURCHASED, "BUY", 4),
            ("PARAFUSO-M4", "Parafuso M4", Item.ItemType.PURCHASED, "BUY", 3),
            ("PARAFUSO-M4-ALT", "Parafuso M4 alternativo", Item.ItemType.PURCHASED, "BUY", 3),
        ]
        items = {}
        for code, desc, item_type, source, lead in item_data:
            item, _ = Item.objects.get_or_create(
                code=code, defaults={"description": desc, "item_type": item_type}
            )
            items[code] = item
            ItemPlantPolicy.objects.update_or_create(
                plant=plant,
                item=item,
                defaults={
                    "source_type": source,
                    "lead_time_days": lead,
                    "safety_stock": Decimal("5") if source == "BUY" else Decimal("0"),
                    "lot_sizing_rule": ItemPlantPolicy.LotSizingRule.MULTIPLE if source == "BUY" else ItemPlantPolicy.LotSizingRule.LOT_FOR_LOT,
                    "order_multiple": Decimal("10") if source == "BUY" else Decimal("1"),
                },
            )

        bom = [
            ("FAROL-H7", "CONJ-OPTICO", 1, 10),
            ("FAROL-H7", "CARCACA", 1, 20),
            ("FAROL-H7", "CHICOTE", 1, 30),
            ("FAROL-H7", "LAMPADA-H7", 1, 40),
            ("FAROL-H7", "PARAFUSO-M4", 4, 50),
            ("CONJ-OPTICO", "REFLETOR", 1, 10),
            ("CONJ-OPTICO", "LENTE", 1, 20),
        ]
        for parent, component, qty, seq in bom:
            BOMLine.objects.update_or_create(
                parent=items[parent],
                component=items[component],
                sequence=seq,
                defaults={"quantity_per": Decimal(str(qty)), "is_active": True},
            )

        supplier, _ = Supplier.objects.get_or_create(
            code="SUP-001", defaults={"name": "Fornecedor Componentes Brasil"}
        )
        for code in ["CARCACA", "REFLETOR", "LENTE", "CHICOTE", "LAMPADA-H7", "PARAFUSO-M4", "PARAFUSO-M4-ALT"]:
            ItemSupplier.objects.update_or_create(
                plant=plant,
                item=items[code],
                supplier=supplier,
                defaults={"is_primary": True, "lead_time_days": 7, "unit_price": Decimal("10")},
            )
            StockBalance.objects.update_or_create(
                item=items[code],
                location=location,
                defaults={"on_hand": Decimal("20"), "allocated": Decimal("0")},
            )


        ItemSubstitute.objects.update_or_create(
            plant=plant,
            item=items["PARAFUSO-M4"],
            substitute_item=items["PARAFUSO-M4-ALT"],
            defaults={
                "priority": 10,
                "substitute_quantity_per_primary": Decimal("1"),
                "is_active": True,
            },
        )

        assembly_wc, _ = WorkCenter.objects.get_or_create(
            plant=plant, code="MONT", defaults={"name": "Montagem", "capacity_hours_per_day": 16}
        )
        test_wc, _ = WorkCenter.objects.get_or_create(
            plant=plant, code="TESTE", defaults={"name": "Teste elétrico", "capacity_hours_per_day": 8, "is_critical": True}
        )
        routing, _ = Routing.objects.get_or_create(
            plant=plant, item=items["FAROL-H7"], code="STD", version=1
        )
        RoutingOperation.objects.update_or_create(
            routing=routing,
            sequence=10,
            defaults={
                "description": "Montar conjunto do farol",
                "work_center": assembly_wc,
                "setup_hours": Decimal("0.5"),
                "run_hours_per_unit": Decimal("0.10"),
            },
        )
        RoutingOperation.objects.update_or_create(
            routing=routing,
            sequence=20,
            defaults={
                "description": "Testar e inspecionar",
                "work_center": test_wc,
                "setup_hours": Decimal("0.25"),
                "run_hours_per_unit": Decimal("0.05"),
            },
        )

        optical_routing, _ = Routing.objects.get_or_create(
            plant=plant, item=items["CONJ-OPTICO"], code="STD", version=1
        )
        RoutingOperation.objects.update_or_create(
            routing=optical_routing,
            sequence=10,
            defaults={
                "description": "Montar conjunto óptico",
                "work_center": assembly_wc,
                "setup_hours": Decimal("0.25"),
                "run_hours_per_unit": Decimal("0.06"),
            },
        )

        for work_center, hours in [(assembly_wc, Decimal("8")), (test_wc, Decimal("8"))]:
            for weekday in range(5):
                WorkCenterShift.objects.update_or_create(
                    work_center=work_center,
                    weekday=weekday,
                    name="Turno 1",
                    defaults={
                        "start_time": time(7, 0),
                        "end_time": time(16, 0),
                        "capacity_hours": hours,
                        "efficiency_percent": Decimal("90"),
                        "is_active": True,
                    },
                )

        MasterProductionSchedule.objects.update_or_create(
            plant=plant,
            item=items["FAROL-H7"],
            due_date=today + timedelta(days=30),
            source="DEMO",
            defaults={"quantity": Decimal("100"), "status": MasterProductionSchedule.Status.FIRM},
        )
        self.stdout.write(self.style.SUCCESS("Dados de demonstração criados."))
