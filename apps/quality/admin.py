from django.contrib import admin
from .models import Disposition, InspectionCharacteristic, InspectionOrder, InspectionPlan, InspectionResult, NonConformance

admin.site.register([InspectionPlan, InspectionCharacteristic, InspectionOrder, InspectionResult, NonConformance, Disposition])
