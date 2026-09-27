from django.shortcuts import get_object_or_404
from rest_framework import permissions, viewsets

from apps.agents.models import Agent, AgentTool
from apps.agents.serializers import AgentSerializer, AgentToolSerializer
from apps.agents.services import provision_default_tools
from apps.core.permissions import IsBusinessMember, TenantScopedQuerySetMixin


class AgentViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = AgentSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = Agent.objects.all().prefetch_related("tools")

    def perform_create(self, serializer):
        agent = serializer.save(business=self.request.business)
        provision_default_tools(agent)


class AgentToolViewSet(viewsets.ModelViewSet):
    """Nested under an agent: /agents/{agent_id}/tools/"""

    serializer_class = AgentToolSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]

    def get_agent(self):
        return get_object_or_404(Agent, pk=self.kwargs["agent_pk"], business=self.request.business)

    def get_queryset(self):
        return AgentTool.objects.filter(agent_id=self.kwargs["agent_pk"], business=self.request.business)

    def perform_create(self, serializer):
        agent = self.get_agent()
        serializer.save(business=self.request.business, agent=agent)
