from django.core.management.base import BaseCommand
from apps.demand.models import SalesOrderLine
from apps.integrated_scheduling.models import OTIFLineResult
from apps.integrated_scheduling.service_level import evaluate_otif_queryset, service_level_summary
class Command(BaseCommand):
    help='Calcula OTIF por linha de pedido e resume nível de serviço.'
    def add_arguments(self,p):
        p.add_argument('--plant')
        p.add_argument('--from-date')
        p.add_argument('--to-date')
        p.add_argument('--reference',default='CUSTOMER_ACCEPTED',choices=['REQUESTED','APPROVED_PROMISE','CUSTOMER_ACCEPTED'])
    def handle(self,*args,**o):
        qs=SalesOrderLine.objects.exclude(sales_order__status='CANCELLED')
        if o['plant']: qs=qs.filter(sales_order__plant__code=o['plant'])
        if o['from_date']: qs=qs.filter(requested_date__gte=o['from_date'])
        if o['to_date']: qs=qs.filter(requested_date__lte=o['to_date'])
        evaluate_otif_queryset(qs,o['reference'])
        rs=OTIFLineResult.objects.filter(reference=o['reference'],sales_order_line__in=qs)
        x=service_level_summary(rs)
        self.stdout.write(self.style.SUCCESS(f"OTIF={x['otif_pct']}% OnTime={x['on_time_pct']}% InFull={x['in_full_pct']}% linhas={x['lines']}"))
