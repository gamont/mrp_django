import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.common.models import Plant
from apps.masterdata.models import Item, Supplier
from apps.production.models import WorkOrder
from apps.purchasing.models import PurchaseOrder


@pytest.mark.django_db
def test_work_order_detail_requires_login(client):
    assert client.get('/production/orders/1/').status_code == 302


@pytest.mark.django_db
def test_work_order_detail_renders_for_selected_plant(client):
    user = get_user_model().objects.create_user(username='detail-user', password='test12345')
    plant = Plant.objects.create(code='D01', name='Detalhe')
    item = Item.objects.create(code='DET-001', description='Item detalhe', item_type='MANUFACTURED', uom='UN')
    wo = WorkOrder.objects.create(number='OP-DET-001', plant=plant, item=item, quantity=10, release_date=timezone.localdate(), due_date=timezone.localdate())
    client.force_login(user)
    session=client.session; session['ui_plant_id']=plant.pk; session.save()
    response=client.get(reverse('ui:work-order-detail', args=[wo.pk]))
    assert response.status_code == 200
    assert b'OP-DET-001' in response.content


@pytest.mark.django_db
def test_purchase_order_detail_renders(client):
    user = get_user_model().objects.create_user(username='buyer-detail', password='test12345')
    plant = Plant.objects.create(code='D02', name='Detalhe 2')
    supplier = Supplier.objects.create(code='SUP-D', name='Fornecedor detalhe')
    po = PurchaseOrder.objects.create(number='OC-DET-001', plant=plant, supplier=supplier, order_date=timezone.localdate(), expected_date=timezone.localdate())
    client.force_login(user)
    session=client.session; session['ui_plant_id']=plant.pk; session.save()
    response=client.get(reverse('ui:purchase-order-detail', args=[po.pk]))
    assert response.status_code == 200
    assert b'OC-DET-001' in response.content
