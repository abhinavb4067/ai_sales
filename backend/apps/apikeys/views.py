from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apikeys.models import ApiKey, UsageEvent
from apps.apikeys.serializers import ApiKeyCreateSerializer, ApiKeySerializer
from apps.core.permissions import IsBusinessMember, TenantScopedQuerySetMixin


class ApiKeyListCreateView(TenantScopedQuerySetMixin, generics.ListCreateAPIView):
    serializer_class = ApiKeySerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]
    queryset = ApiKey.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = ApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance, raw_key = ApiKey.generate(
            business=request.business,
            name=serializer.validated_data["name"],
            created_by=request.user,
        )

        data = ApiKeySerializer(instance).data
        # Only time the raw secret is ever exposed — not retrievable again.
        data["key"] = raw_key
        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]

    def post(self, request, pk):
        api_key = get_object_or_404(ApiKey, pk=pk, business=request.business)
        api_key.status = ApiKey.Status.REVOKED
        api_key.revoked_at = timezone.now()
        api_key.save(update_fields=["status", "revoked_at", "updated_at"])
        return Response(ApiKeySerializer(api_key).data)


class UsageSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]

    def get(self, request):
        qs = UsageEvent.objects.filter(business=request.business)
        totals = qs.aggregate(
            total_messages=Count("id"),
            total_input_tokens=Sum("input_tokens"),
            total_output_tokens=Sum("output_tokens"),
        )
        by_channel = list(qs.values("channel").annotate(messages=Count("id")).order_by("channel"))
        return Response(
            {
                "total_messages": totals["total_messages"] or 0,
                "total_input_tokens": totals["total_input_tokens"] or 0,
                "total_output_tokens": totals["total_output_tokens"] or 0,
                "by_channel": by_channel,
            }
        )
