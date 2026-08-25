from django.contrib import admin
from .models import RecallAction, RecallAffectedUnit, RecallCase, RecallCriterion

admin.site.register(RecallCase)
admin.site.register(RecallCriterion)
admin.site.register(RecallAffectedUnit)
admin.site.register(RecallAction)
