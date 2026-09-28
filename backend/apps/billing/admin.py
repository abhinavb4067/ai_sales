from django.contrib import admin

from apps.billing.models import Plan, Subscription

admin.site.register(Plan)
admin.site.register(Subscription)
