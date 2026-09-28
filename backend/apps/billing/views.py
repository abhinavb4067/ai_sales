from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import Plan, Subscription
from apps.billing.serializers import ChangePlanSerializer, PlanSerializer, SubscriptionSerializer
from apps.billing.services import activate_subscription, get_current_usage_count
from apps.core.permissions import HasRole, IsBusinessMember


class PlanListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        plans = Plan.objects.filter(is_active=True, is_public=True)
        return Response(PlanSerializer(plans, many=True).data)


class SubscriptionDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember]

    def get(self, request):
        subscription = get_object_or_404(Subscription, business=request.business)
        data = SubscriptionSerializer(subscription).data
        data["messages_used_this_period"] = get_current_usage_count(request.business, subscription)
        return Response(data)


class ChangePlanView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember, HasRole.roles("owner", "admin")]

    def post(self, request):
        serializer = ChangePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan = get_object_or_404(Plan, code=serializer.validated_data["plan_code"], is_active=True)
        subscription = activate_subscription(business=request.business, plan=plan)
        return Response(SubscriptionSerializer(subscription).data)
