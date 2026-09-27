from django.contrib import admin

from apps.agents.models import Agent, AgentSetting, AgentTool


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "agent_type", "primary_goal", "status", "created_at"]
    list_filter = ["agent_type", "primary_goal", "status"]
    search_fields = ["name", "business__name"]


admin.site.register(AgentSetting)
admin.site.register(AgentTool)
