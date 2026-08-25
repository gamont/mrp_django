from datetime import date
from decimal import Decimal
from django.test import TestCase
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.demand.models import SalesOrder, SalesOrderLine
from apps.integrated_scheduling.models import SalesOrderPromise, CustomerPromiseResponse, CommercialServiceCase
from apps.integrated_scheduling.commercial_confirmation import record_customer_response, effective_customer_commitment_date

class CustomerConfirmation075Tests(TestCase):
    def setUp(self):
        self.plant=Plant.objects.create(code='SP01', name='São Paulo')
        self.item=Item.objects.create(code='FG-1', description='Produto', item_type=Item.ItemType.FINISHED)
        self.order=SalesOrder.objects.create(number='SO-075', plant=self.plant, customer_code='C1', customer_name='Cliente', order_date=date(2026,8,1), requested_date=date(2026,8,10), status=SalesOrder.Status.CONFIRMED)
        self.line=SalesOrderLine.objects.create(sales_order=self.order, line_number=10, item=self.item, quantity=Decimal('10'), requested_date=date(2026,8,10))
        self.promise=SalesOrderPromise.objects.create(sales_order_line=self.line, source=SalesOrderPromise.Source.MANUAL, proposed_date=date(2026,8,12), quantity=Decimal('10'), status=SalesOrderPromise.Status.APPROVED)
        CommercialServiceCase.objects.create(sales_order_line=self.line, promise=self.promise)

    def test_acceptance_becomes_effective_mrp_date(self):
        record_customer_response(self.promise, response='ACCEPTED', confirmed_date=date(2026,8,12), reevaluate=False)
        self.assertEqual(effective_customer_commitment_date(self.line), date(2026,8,12))
        self.assertTrue(CustomerPromiseResponse.objects.filter(promise=self.promise, response='ACCEPTED').exists())
        self.assertEqual(self.promise.service_cases.get().status, CommercialServiceCase.Status.CLOSED)

    def test_without_acceptance_keeps_contract_requested_date(self):
        self.assertEqual(effective_customer_commitment_date(self.line), date(2026,8,10))
