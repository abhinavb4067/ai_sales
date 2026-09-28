from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.ai.providers.base import AIResponse, Usage
from apps.billing.models import Plan, Subscription
from apps.billing.services import activate_subscription, enforce_subscription_and_limits
from apps.core.exceptions import APIError
from apps.core.testing import authenticated_client, create_business_with_owner


class FakeProvider:
    def generate(self, messages, tools=None, temperature=0.4, max_tokens=800):
        return AIResponse(content="Hi", tool_calls=[], usage=Usage(input_tokens=10, output_tokens=5), finish_reason="stop")

    def embed(self, texts):
        raise NotImplementedError

    def count_tokens(self, text):
        return len(text) // 4


class TrialSubscriptionSignalTests(APITestCase):
    def test_business_creation_auto_starts_trial_on_default_plan(self):
        _, business = create_business_with_owner()
        subscription = business.subscription
        self.assertEqual(subscription.status, Subscription.Status.TRIAL)
        self.assertEqual(subscription.plan.code, "starter")
        self.assertIsNotNone(subscription.trial_ends_at)


class EnforceSubscriptionTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()

    def test_trial_subscription_allows_requests(self):
        enforce_subscription_and_limits(self.business)  # should not raise

    def test_suspended_subscription_blocks_requests(self):
        sub = self.business.subscription
        sub.status = Subscription.Status.SUSPENDED
        sub.save(update_fields=["status"])
        with self.assertRaises(APIError) as ctx:
            enforce_subscription_and_limits(self.business)
        self.assertEqual(ctx.exception.code, "SUBSCRIPTION_INACTIVE")
        self.assertEqual(ctx.exception.status_code, 402)

    def test_usage_over_plan_limit_blocks_requests(self):
        from apps.apikeys.models import UsageEvent

        agent = Agent.objects.create(business=self.business, name="A")
        sub = self.business.subscription
        limit = sub.plan.max_messages_per_month
        for _ in range(limit):
            UsageEvent.objects.create(business=self.business, agent=agent, channel="api")

        with self.assertRaises(APIError) as ctx:
            enforce_subscription_and_limits(self.business)
        self.assertEqual(ctx.exception.code, "USAGE_LIMIT_EXCEEDED")
        self.assertEqual(ctx.exception.status_code, 429)

    def test_activate_subscription_switches_plan_and_status(self):
        growth = Plan.objects.get(code="growth")
        sub = activate_subscription(business=self.business, plan=growth)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertEqual(sub.plan_id, growth.id)


class ChatPipelineBillingTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)
        self.agent = Agent.objects.create(business=self.business, name="Test Agent", status=Agent.Status.ACTIVE)

    @patch("apps.ai.orchestrator.get_provider_for_agent", return_value=FakeProvider())
    def test_playground_chat_blocked_when_subscription_suspended(self, mock_provider):
        sub = self.business.subscription
        sub.status = Subscription.Status.SUSPENDED
        sub.save(update_fields=["status"])

        response = self.client_auth.post(
            "/api/v1/playground/chat/", {"agent_id": self.agent.id, "message": "Hi"}, format="json"
        )
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.data["error"]["code"], "SUBSCRIPTION_INACTIVE")


class BillingApiTests(APITestCase):
    def setUp(self):
        self.user, self.business = create_business_with_owner()
        self.client_auth = authenticated_client(self.user)

    def test_plan_list_is_public(self):
        response = self.client.get("/api/v1/billing/plans/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = {p["code"] for p in response.data}
        self.assertEqual(codes, {"starter", "growth", "scale"})

    def test_subscription_detail_includes_usage(self):
        response = self.client_auth.get("/api/v1/billing/subscription/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["plan"]["code"], "starter")
        self.assertEqual(response.data["messages_used_this_period"], 0)

    def test_change_plan_requires_owner_or_admin_role(self):
        response = self.client_auth.post("/api/v1/billing/subscription/change-plan/", {"plan_code": "growth"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["plan"]["code"], "growth")

    def test_other_business_subscription_is_isolated(self):
        other_user, other_business = create_business_with_owner(business_name="Other Co", email="other@example.com")
        other_client = authenticated_client(other_user)

        response = other_client.get("/api/v1/billing/subscription/")
        self.assertEqual(response.data["plan"]["code"], "starter")
        self.assertNotEqual(response.data["plan"]["code"], "growth")
