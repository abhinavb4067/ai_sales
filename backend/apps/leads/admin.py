from django.contrib import admin

from apps.leads.models import Lead, LeadActivity, LeadStage

admin.site.register(LeadStage)
admin.site.register(Lead)
admin.site.register(LeadActivity)
