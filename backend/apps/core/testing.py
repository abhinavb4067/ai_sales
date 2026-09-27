"""Shared test helpers."""
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.tenants.models import Business, BusinessMembership


def create_business_with_owner(*, business_name="Test Co", email="owner@example.com", password="StrongPass123!"):
    user = User.objects.create_user(email=email, password=password, name="Owner")
    business = Business.objects.create(name=business_name, owner=user, email=email)
    BusinessMembership.objects.create(
        user=user, business=business, role=BusinessMembership.Role.OWNER, status=BusinessMembership.Status.ACTIVE
    )
    return user, business


def authenticated_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client
