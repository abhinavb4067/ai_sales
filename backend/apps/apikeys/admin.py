from django.contrib import admin

from apps.apikeys.models import ApiKey, UsageEvent

admin.site.register(ApiKey)
admin.site.register(UsageEvent)
