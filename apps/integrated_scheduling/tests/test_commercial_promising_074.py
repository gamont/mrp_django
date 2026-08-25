from datetime import date
from decimal import Decimal
from django.test import TestCase
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.demand.models import SalesOrder, SalesOrderLine
from apps.integrated_scheduling.models import SalesOrderPromise
from apps.integrated_scheduling.commercial_promising import approve_promise

class CommercialPromising074Tests(TestCase):
    def setUp(self):
        self.plant=Plant.objects.create(code="SP01", name="São Paulo")
        self.item=Item.objects.create(code="FG-074", description="Finished good")
        self.order=SalesOrder.objects.create(number="SO-074", plant=self.plant, customer_code="C1", customer_name="Cliente 1", order_date=date(2026,8,1), requested_date=date(2026,8,20), status=SalesOrder.Status.CONFIRMED)
        self.line=SalesOrderLine.objects.create(sales_order=self.order, line_number=10, item=self.item, quantity=Decimal("10"), requested_date=date(2026,8,20))

    def test_approval_supersedes_previous_promise(self):
        old=SalesOrderPromise.objects.create(sales_order_line=self.line, source="MANUAL", proposed_date=date(2026,8,20), quantity=Decimal("10"), status=SalesOrderPromise.Status.APPROVED)
        new=SalesOrderPromise.objects.create(sales_order_line=self.line, source="RECOVERY", proposed_date=date(2026,8,22), previous_approved_date=old.proposed_date, quantity=Decimal("10"))
        approve_promise(new)
        old.refresh_from_db(); new.refresh_from_db()
        self.assertEqual(old.status, SalesOrderPromise.Status.SUPERSEDED)
        self.assertEqual(new.status, SalesOrderPromise.Status.APPROVED)
