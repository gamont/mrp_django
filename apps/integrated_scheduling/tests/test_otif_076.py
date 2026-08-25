from datetime import date
from decimal import Decimal
from django.test import TestCase
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.demand.models import SalesOrder, SalesOrderLine, SalesDelivery, SalesDeliveryLine
from apps.integrated_scheduling.service_level import evaluate_otif_line
class OTIF076Test(TestCase):
    def test_full_on_time_delivery_is_otif(self):
        p=Plant.objects.create(code='T1',name='Test')
        item=Item.objects.create(code='IT076',description='Item',item_type='FINISHED')
        so=SalesOrder.objects.create(number='SO076',plant=p,customer_code='C1',customer_name='Cliente',order_date=date(2026,8,1),requested_date=date(2026,8,10),status='CONFIRMED')
        line=SalesOrderLine.objects.create(sales_order=so,line_number=10,item=item,quantity=Decimal('10'),requested_date=date(2026,8,10))
        d=SalesDelivery.objects.create(number='DEL076',plant=p,delivery_date=date(2026,8,10))
        SalesDeliveryLine.objects.create(delivery=d,sales_order_line=line,quantity=Decimal('10'))
        r=evaluate_otif_line(line,'REQUESTED')
        self.assertTrue(r.on_time); self.assertTrue(r.in_full); self.assertTrue(r.otif)
