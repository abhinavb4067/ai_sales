from django.contrib import admin

from apps.integrations.models import Integration, WebhookDelivery

admin.site.register(Integration)
admin.site.register(WebhookDelivery)
