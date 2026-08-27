import json
import os
import unittest
from unittest.mock import patch

from founder_control_center.app import create_app
from founder_control_center.readiness import readiness_snapshot


class ReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()

    def test_readiness_reports_configuration_without_secret_material(self):
        values = {
            "FCC_ADMIN_TOKEN": "admin-secret-value-long",
            "FCC_SESSION_SECRET": "session-secret-value-long-enough-32-bytes",
            "FCC_FACTORY_INGEST_TOKEN": "factory-secret-value",
            "FCC_METRIC_INGEST_TOKEN": "metric-secret-value",
            "FCC_GITHUB_TOKEN": "github-secret-value",
            "FCC_DB": "/tmp/private-control.db",
            "FCC_SECURE_COOKIE": "1",
        }
        with patch.dict(os.environ, values, clear=False):
            response = self.client.get("/api/readiness")
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["private_access"]["state"], "CONFIGURED")
            self.assertEqual(payload["factory_feed"]["state"], "CONFIGURED")
            self.assertEqual(payload["business_metric_feed"]["state"], "CONFIGURED")
            self.assertEqual(payload["private_github"]["state"], "CONFIGURED")
            self.assertTrue(payload["private_github"]["token_configured"])
            self.assertEqual(payload["health_network_policy"]["state"], "PARTIAL")
            self.assertIn("DNS rebinding", payload["health_network_policy"]["claim"])
            serialized = json.dumps(payload)
            for secret in values.values():
                self.assertNotIn(secret, serialized)

    def test_dashboard_does_not_render_health_network_policy_as_green(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Health network isolation", response.data)
        self.assertIn(b"PARTIAL", response.data)
        self.assertIn(b"DNS rebinding", response.data)

    def test_dashboard_surfaces_private_github_and_persistence_readiness(self):
        values = {
            "FCC_GITHUB_TOKEN": "github-secret-value",
            "FCC_DB": "/tmp/private-control.db",
        }
        with patch.dict(os.environ, values, clear=False):
            response = self.client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Private GitHub", response.data)
            self.assertIn(b"optional server-side token configured", response.data)
            self.assertIn(b"Persistence path", response.data)
            self.assertIn(b"explicit database path configured", response.data)

    def test_dashboard_identifies_present_but_unusable_github_token(self):
        with patch.dict(os.environ, {"FCC_GITHUB_TOKEN": "tiny"}, clear=False):
            response = self.client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Private GitHub", response.data)
            self.assertIn(b"present but unusable", response.data)

    def test_weak_present_secrets_are_blocked_not_configured(self):
        values = {
            "FCC_ADMIN_TOKEN": "short",
            "FCC_SESSION_SECRET": "also-short",
            "FCC_FACTORY_INGEST_TOKEN": "tiny",
            "FCC_METRIC_INGEST_TOKEN": "tiny",
            "FCC_GITHUB_TOKEN": "tiny",
        }
        with patch.dict(os.environ, values, clear=True):
            payload = readiness_snapshot()
            self.assertEqual(payload["private_access"]["state"], "BLOCKED")
            self.assertTrue(payload["private_access"]["admin_token_present"])
            self.assertFalse(payload["private_access"]["admin_token_configured"])
            self.assertTrue(payload["private_access"]["session_secret_present"])
            self.assertFalse(payload["private_access"]["session_secret_configured"])
            self.assertEqual(payload["factory_feed"]["state"], "NOT_CONFIGURED")
            self.assertTrue(payload["factory_feed"]["token_present"])
            self.assertFalse(payload["factory_feed"]["token_configured"])
            self.assertEqual(payload["business_metric_feed"]["state"], "NOT_CONFIGURED")
            self.assertEqual(payload["private_github"]["state"], "OPTIONAL_NOT_CONFIGURED")
            self.assertTrue(payload["private_github"]["token_present"])
            self.assertFalse(payload["private_github"]["token_configured"])
            self.assertEqual(payload["health_network_policy"]["state"], "PARTIAL")

    def test_missing_required_private_access_is_blocked_not_green(self):
        with patch.dict(os.environ, {}, clear=True):
            payload = readiness_snapshot()
            self.assertEqual(payload["private_access"]["state"], "BLOCKED")
            self.assertEqual(payload["factory_feed"]["state"], "NOT_CONFIGURED")
            self.assertEqual(payload["business_metric_feed"]["state"], "NOT_CONFIGURED")
            self.assertEqual(payload["private_github"]["state"], "OPTIONAL_NOT_CONFIGURED")
            self.assertFalse(payload["private_github"]["token_present"])
            self.assertFalse(payload["private_github"]["token_configured"])
            self.assertEqual(payload["two_factor"]["state"], "NOT_CONNECTED")
            self.assertEqual(payload["health_network_policy"]["state"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
