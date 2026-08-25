import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.common.models import Plant
from apps.engineering.models import BOMRevision, BOMRevisionLine, EngineeringChange, EngineeringChangeApproval, EngineeringChangeItem
from apps.engineering.services import activate_change, analyze_impact, approve_change, submit_change
from apps.masterdata.models import BOMLine, Item

@pytest.mark.django_db
def test_eco_workflow_activates_revision():
    user=get_user_model().objects.create_user(username="eng",password="x")
    plant=Plant.objects.create(code="SP",name="SP")
    parent=Item.objects.create(code="P",description="Produto",item_type="FINISHED")
    old=Item.objects.create(code="OLD",description="Antigo",item_type="PURCHASED")
    new=Item.objects.create(code="NEW",description="Novo",item_type="PURCHASED")
    BOMLine.objects.create(parent=parent,component=old,quantity_per=1)
    eco=EngineeringChange.objects.create(number="ECO-001",plant=plant,title="Troca",reason="Melhoria",effectivity_type="IMMEDIATE",requested_by=user)
    EngineeringChangeItem.objects.create(change=eco,affected_item=old,action="REPLACE",replacement_item=new,field_name="component")
    EngineeringChangeApproval.objects.create(change=eco,sequence=1,role="Engenharia")
    rev=BOMRevision.objects.create(plant=plant,parent=parent,revision="B",change=eco)
    BOMRevisionLine.objects.create(revision=rev,sequence=10,component=new,quantity_per=1)
    analyze_impact(eco,user); submit_change(eco,user); approve_change(eco,user); activate_change(eco,user)
    eco.refresh_from_db(); assert eco.status=="EFFECTIVE"
    assert BOMLine.objects.filter(parent=parent,component=new,is_active=True).exists()
    assert not BOMLine.objects.filter(parent=parent,component=old,is_active=True).exists()
