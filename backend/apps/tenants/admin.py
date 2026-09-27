from django.contrib import admin

from apps.tenants.models import Business, BusinessMembership


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "industry", "created_at"]
    search_fields = ["name", "email"]


@admin.register(BusinessMembership)
class BusinessMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "business", "role", "status"]
    list_filter = ["role", "status"]
