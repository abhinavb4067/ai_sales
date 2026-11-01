from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents.models import Agent
from apps.apikeys.models import UsageEvent
from apps.billing.models import Subscription
from apps.conversations.models import Conversation
from apps.integrations.models import WebhookDelivery
from apps.superadmin.permissions import IsPlatformSuperAdmin
from apps.superadmin.serializers import SuperAdminAgentSerializer, SuperAdminBusinessSerializer
from apps.tenants.models import Business


class SuperAdminBusinessListView(generics.ListAPIView):
    """All tenants, platform-wide — deliberately NOT TenantScopedQuerySetMixin,
    since Super Admin is the one place cross-tenant visibility is the point."""

    serializer_class = SuperAdminBusinessSerializer
    permission_classes = [permissions.IsAuthenticated, IsPlatformSuperAdmin]
    queryset = (
        Business.objects.select_related("owner", "subscription", "subscription__plan")
        .annotate(agent_count=Count("agents", distinct=True), member_count=Count("memberships", distinct=True))
        .order_by("-created_at")
    )


class SuperAdminBusinessSuspendView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPlatformSuperAdmin]

    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        subscription = getattr(business, "subscription", None)
        if subscription is None:
            return Response({"detail": "This business has no subscription to suspend."}, status=status.HTTP_404_NOT_FOUND)
        subscription.status = Subscription.Status.SUSPENDED
        subscription.save(update_fields=["status", "updated_at"])
        return Response({"status": subscription.status})


class SuperAdminBusinessReactivateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPlatformSuperAdmin]

    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        subscription = getattr(business, "subscription", None)
        if subscription is None:
            return Response({"detail": "This business has no subscription to reactivate."}, status=status.HTTP_404_NOT_FOUND)
        subscription.status = Subscription.Status.ACTIVE
        subscription.save(update_fields=["status", "updated_at"])
        return Response({"status": subscription.status})


class SuperAdminAgentListView(generics.ListAPIView):
    serializer_class = SuperAdminAgentSerializer
    permission_classes = [permissions.IsAuthenticated, IsPlatformSuperAdmin]
    queryset = Agent.objects.select_related("business").order_by("-created_at")


class SuperAdminPlatformHealthView(APIView):
    """Coarse, cheap-to-compute platform-wide counters (master spec
    section 17: "Use aggregated tables or background jobs for expensive
    analytics. Do not run costly unbounded aggregation queries on every
    dashboard request.") — every number here is either a simple count or
    scoped to the last 30 days, never a full-table scan of messages."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformSuperAdmin]

    def get(self, request):
        since_30d = timezone.now() - timedelta(days=30)

        subscription_counts = dict(
            Subscription.objects.values_list("status").annotate(count=Count("id"))
        )
        failed_webhooks_30d = WebhookDelivery.objects.filter(
            created_at__gte=since_30d, processed=False
        ).count()
        usage_30d = UsageEvent.objects.filter(created_at__gte=since_30d).count()

        return Response(
            {
                "total_businesses": Business.objects.count(),
                "total_agents": Agent.objects.count(),
                "total_conversations": Conversation.objects.count(),
                "conversations_last_30d": Conversation.objects.filter(created_at__gte=since_30d).count(),
                "ai_responses_last_30d": usage_30d,
                "failed_webhook_deliveries_last_30d": failed_webhooks_30d,
                "subscriptions_by_status": subscription_counts,
            }
        )
