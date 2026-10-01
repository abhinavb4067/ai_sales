from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import Plan, Subscription
from apps.billing.providers.base import WebhookVerificationError
from apps.billing.providers.registry import get_payment_provider
from apps.billing.serializers import ChangePlanSerializer, PlanSerializer, SubscriptionSerializer
from apps.billing.services import (
    cancel_subscription_for_business,
    get_current_usage_count,
    handle_razorpay_webhook_event,
    initiate_plan_change,
)
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
    """Manual provider: activates the plan immediately. Any real gateway
    (Razorpay): starts a checkout and hands the frontend what it needs to
    collect payment — the subscription doesn't change until a verified
    webhook confirms it (see RazorpayWebhookView)."""

    permission_classes = [permissions.IsAuthenticated, IsBusinessMember, HasRole.roles("owner", "admin")]

    def post(self, request):
        serializer = ChangePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan = get_object_or_404(Plan, code=serializer.validated_data["plan_code"], is_active=True)
        result = initiate_plan_change(request.business, plan)

        if result["type"] == "activated":
            return Response(SubscriptionSerializer(result["subscription"]).data)
        return Response({"type": "checkout", "checkout_url": result["checkout_url"], "client_data": result["client_data"]})


class CancelSubscriptionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBusinessMember, HasRole.roles("owner", "admin")]

    def post(self, request):
        subscription = cancel_subscription_for_business(request.business)
        return Response(SubscriptionSerializer(subscription).data)


class RazorpayWebhookView(APIView):
    """Public endpoint — authenticated entirely by the webhook signature,
    never a session/JWT/API key, same as every payment gateway's webhook
    contract. Always verify before trusting anything in the body."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        provider = get_payment_provider()
        try:
            event = provider.construct_webhook_event(payload=request.body, headers=request.headers)
        except WebhookVerificationError:
            return Response(status=400)

        handle_razorpay_webhook_event(event)
        return Response(status=200)
