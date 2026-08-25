from datetime import date
from decimal import Decimal
from django.test import TestCase
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.demand.models import SalesOrder, SalesOrderLine, SalesDelivery, SalesDeliveryLine
from apps.integrated_scheduling.models import ServiceLevelTarget
from apps.integrated_scheduling.service_level import evaluate_otif_line
from apps.integrated_scheduling.service_level_analytics import analytics

class ServiceLevel077Test(TestCase):
    def test_fill_rate_and_target(self):
        plant=Plant.objects.create(code='SP01',name='SP')
        item=Item.objects.create(code='A',description='A',item_type='FINISHED',uom='EA')
        so=SalesOrder.objects.create(number='SO1',plant=plant,customer_code='C1',customer_name='Cliente',order_date=date(2026,8,1),requested_date=date(2026,8,10),status='CONFIRMED')
        line=SalesOrderLine.objects.create(sales_order=so,line_number=10,item=item,quantity=Decimal('10'),delivered_quantity=Decimal('5'),requested_date=date(2026,8,10))
        d=SalesDelivery.objects.create(number='D1',plant=plant,delivery_date=date(2026,8,10))
        SalesDeliveryLine.objects.create(delivery=d,sales_order_line=line,quantity=Decimal('5'))
        ServiceLevelTarget.objects.create(plant=plant,scope='CUSTOMER',scope_key='C1',scope_label='Cliente',effective_from=date(2026,8,1),otif_target_pct=Decimal('95'))
        r=evaluate_otif_line(line,'REQUESTED')
        rows=analytics([r],'CUSTOMER',date(2026,8,10))
        self.assertEqual(rows[0]['fill_rate_pct'],Decimal('50.0'))
        self.assertFalse(rows[0]['target_met'])
