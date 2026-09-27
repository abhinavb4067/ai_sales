from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.tenants.models import Business, BusinessMembership


class RegistrationTests(APITestCase):
    def test_register_creates_user_business_and_owner_membership(self):
        url = reverse("auth-register")
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "SuperSecret123!",
            "business_name": "Jane's Bakery",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIn("tokens", response.data)
        self.assertTrue(User.objects.filter(email="jane@example.com").exists())

        business = Business.objects.get(name="Jane's Bakery")
        membership = BusinessMembership.objects.get(business=business)
        self.assertEqual(membership.role, BusinessMembership.Role.OWNER)
        self.assertEqual(membership.status, BusinessMembership.Status.ACTIVE)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(email="dup@example.com", password="SuperSecret123!", name="Dup")
        url = reverse("auth-register")
        payload = {
            "name": "Dup2",
            "email": "dup@example.com",
            "password": "SuperSecret123!",
            "business_name": "Dup Co",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_weak_password(self):
        url = reverse("auth-register")
        payload = {"name": "X", "email": "weak@example.com", "password": "12345", "business_name": "X Co"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_passwords_are_hashed_not_plaintext(self):
        url = reverse("auth-register")
        payload = {
            "name": "Sec",
            "email": "sec@example.com",
            "password": "SuperSecret123!",
            "business_name": "Sec Co",
        }
        self.client.post(url, payload, format="json")
        user = User.objects.get(email="sec@example.com")
        self.assertNotEqual(user.password, "SuperSecret123!")
        self.assertTrue(user.password.startswith("md5$") or "$" in user.password)


class LoginLogoutRefreshTests(APITestCase):
    def setUp(self):
        self.email = "login@example.com"
        self.password = "SuperSecret123!"
        self.user = User.objects.create_user(email=self.email, password=self.password, name="Login")

    def test_login_success(self):
        url = reverse("auth-login")
        response = self.client.post(url, {"email": self.email, "password": self.password}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])

    def test_login_wrong_password_fails(self):
        url = reverse("auth-login")
        response = self.client.post(url, {"email": self.email, "password": "wrong"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_rotates_token_and_blacklists_old_one(self):
        login = self.client.post(
            reverse("auth-login"), {"email": self.email, "password": self.password}, format="json"
        )
        refresh_token = login.data["tokens"]["refresh"]

        refresh_response = self.client.post(reverse("auth-refresh"), {"refresh": refresh_token}, format="json")
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data["tokens"])

        # Old refresh token must now be blacklisted (rotation) — reuse fails.
        reuse_response = self.client.post(reverse("auth-refresh"), {"refresh": refresh_token}, format="json")
        self.assertEqual(reuse_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        login = self.client.post(
            reverse("auth-login"), {"email": self.email, "password": self.password}, format="json"
        )
        access = login.data["tokens"]["access"]
        refresh_token = login.data["tokens"]["refresh"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        logout_response = self.client.post(reverse("auth-logout"), {"refresh": refresh_token}, format="json")
        self.assertEqual(logout_response.status_code, status.HTTP_205_RESET_CONTENT)

        reuse_response = self.client.post(reverse("auth-refresh"), {"refresh": refresh_token}, format="json")
        self.assertEqual(reuse_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_authentication(self):
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
