from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.billing.models import Subscription
from apps.billing.tasks import expire_lapsed_trials, flag_past_due_subscriptions
from apps.core.testing import create_business_with_owner


class ExpireLapsedTrialsTests(TestCase):
    def test_expires_trial_past_its_period_end(self):
        _, business = create_business_with_owner()
        subscription = business.subscription
        subscription.current_period_end = timezone.now() - timedelta(hours=1)
        subscription.save(update_fields=["current_period_end"])

        count = expire_lapsed_trials()

        self.assertEqual(count, 1)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.EXPIRED)

    def test_does_not_touch_trial_still_within_period(self):
        _, business = create_business_with_owner()
        subscription = business.subscription
        subscription.current_period_end = timezone.now() + timedelta(days=5)
        subscription.save(update_fields=["current_period_end"])

        count = expire_lapsed_trials()

        self.assertEqual(count, 0)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.TRIAL)

    def test_does_not_touch_already_active_subscription(self):
        _, business = create_business_with_owner()
        subscription = business.subscription
        subscription.status = Subscription.Status.ACTIVE
        subscription.current_period_end = timezone.now() - timedelta(hours=1)
        subscription.save(update_fields=["status", "current_period_end"])

        count = expire_lapsed_trials()

        self.assertEqual(count, 0)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)


class FlagPastDueSubscriptionsTests(TestCase):
    def test_flags_active_subscription_past_grace_period(self):
        _, business = create_business_with_owner()
        subscription = business.subscription
        subscription.status = Subscription.Status.ACTIVE
        subscription.current_period_end = timezone.now() - timedelta(days=5)
        subscription.save(update_fields=["status", "current_period_end"])

        count = flag_past_due_subscriptions()

        self.assertEqual(count, 1)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.PAST_DUE)

    def test_does_not_flag_within_grace_period(self):
        _, business = create_business_with_owner()
        subscription = business.subscription
        subscription.status = Subscription.Status.ACTIVE
        subscription.current_period_end = timezone.now() - timedelta(hours=1)
        subscription.save(update_fields=["status", "current_period_end"])

        count = flag_past_due_subscriptions()

        self.assertEqual(count, 0)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)

    def test_does_not_flag_trial_subscriptions(self):
        _, business = create_business_with_owner()
        subscription = business.subscription
        subscription.current_period_end = timezone.now() - timedelta(days=5)
        subscription.save(update_fields=["current_period_end"])

        count = flag_past_due_subscriptions()

        self.assertEqual(count, 0)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.TRIAL)
