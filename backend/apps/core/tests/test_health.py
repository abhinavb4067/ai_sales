from django.test import TestCase


class HealthcheckTests(TestCase):
    def test_healthcheck_returns_200_when_dependencies_ok(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["checks"]["database"], "ok")

    def test_healthcheck_is_unauthenticated(self):
        response = self.client.get("/health/")
        self.assertNotEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 403)
