from datetime import date
from decimal import Decimal
from django.test import TestCase
from apps.common.models import Plant
from apps.masterdata.models import Item
from apps.demand.models import Forecast, SalesOrder, SalesOrderLine
from apps.integrated_scheduling.sop import calculate_forecast_accuracy
class SAndOP078Tests(TestCase):
    def test_forecast_accuracy_wape(self):
        plant=Plant.objects.create(code='SP01',name='SP')
        item=Item.objects.create(code='FG1',description='FG',item_type='FINISHED')
        Forecast.objects.create(plant=plant,item=item,period_start=date(2026,8,1),period_end=date(2026,8,31),quantity=Decimal('100'),status='APPROVED')
        so=SalesOrder.objects.create(number='SO1',plant=plant,customer_code='C1',customer_name='Cliente',order_date=date(2026,8,1),requested_date=date(2026,8,15),status='CONFIRMED')
        SalesOrderLine.objects.create(sales_order=so,line_number=10,item=item,quantity=Decimal('80'),requested_date=date(2026,8,15))
        x=calculate_forecast_accuracy(plant,date(2026,8,1),date(2026,8,31))
        self.assertEqual(x.wape_pct,Decimal('25.00')); self.assertEqual(x.forecast_accuracy_pct,Decimal('75.00'))
