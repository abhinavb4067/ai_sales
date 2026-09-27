from django.shortcuts import get_object_or_404
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsBusinessMember, TenantScopedQuerySetMixin
from apps.leads.models import Lead, LeadStage
from apps.leads.serializers import LeadSerializer, LeadStageSerializer
from apps.leads.services import change_stage, log_activity


class LeadStageViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = LeadStageSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = LeadStage.objects.all()


class LeadViewSet(TenantScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = Lead.objects.all().select_related("stage").prefetch_related("activities")
    filterset_fields = ["stage", "agent"]

    def get_queryset(self):
        qs = super().get_queryset()
        stage_id = self.request.query_params.get("stage")
        agent_id = self.request.query_params.get("agent")
        if stage_id:
            qs = qs.filter(stage_id=stage_id)
        if agent_id:
            qs = qs.filter(agent_id=agent_id)
        return qs

    @action(detail=True, methods=["post"])
    def change_stage(self, request, pk=None):
        lead = self.get_object()
        stage_id = request.data.get("stage")
        stage = get_object_or_404(LeadStage, pk=stage_id, business=request.business)
        change_stage(lead, stage, actor_label=request.user.email)
        return Response(LeadSerializer(lead, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def add_note(self, request, pk=None):
        lead = self.get_object()
        note = request.data.get("content", "")
        log_activity(lead, activity_type="note", content=note, actor_label=request.user.email)
        return Response(LeadSerializer(lead, context={"request": request}).data)
