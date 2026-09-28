from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.billing.services import start_trial_subscription
from apps.tenants.models import Business


@receiver(post_save, sender=Business)
def start_trial_on_business_creation(sender, instance, created, **kwargs):
    if not created:
        return
    start_trial_subscription(instance)
