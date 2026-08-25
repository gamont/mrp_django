from rest_framework import serializers

from .models import AssetMeterReading, FailureEvent, MaintenanceAsset, MaintenancePart, MaintenancePlan, MaintenanceWorkOrder


class DynamicSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"


class MaintenanceAssetSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = MaintenanceAsset

class AssetMeterReadingSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = AssetMeterReading

class MaintenancePlanSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = MaintenancePlan

class MaintenanceWorkOrderSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = MaintenanceWorkOrder

class MaintenancePartSerializer(DynamicSerializer):
    remaining_quantity = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    class Meta(DynamicSerializer.Meta): model = MaintenancePart

class FailureEventSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = FailureEvent

from .models import TechnicianSkill, TechnicianProfile, TechnicianSkillAssignment, WorkOrderAssignment, MaintenanceSLA, ConditionReading, ConditionRule

class TechnicianSkillSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = TechnicianSkill

class TechnicianProfileSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = TechnicianProfile

class TechnicianSkillAssignmentSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = TechnicianSkillAssignment

class WorkOrderAssignmentSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = WorkOrderAssignment

class MaintenanceSLASerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = MaintenanceSLA

class ConditionReadingSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = ConditionReading

class ConditionRuleSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = ConditionRule

from .models import MaintenanceRequiredSkill, MaintenancePartReservation, MaintenanceScheduleConflict

class MaintenanceRequiredSkillSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = MaintenanceRequiredSkill

class MaintenancePartReservationSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = MaintenancePartReservation

class MaintenanceScheduleConflictSerializer(DynamicSerializer):
    class Meta(DynamicSerializer.Meta): model = MaintenanceScheduleConflict
