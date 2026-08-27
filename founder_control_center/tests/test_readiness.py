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
            "FCC_ADMIN_TOKEN": "admin-secret-value",
            "FCC_SESSION_SECRET": "session-secret-value",
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
            serialized = json.dumps(payload)
            for secret in values.values():
                self.assertNotIn(secret, serialized)

    def test_missing_required_private_access_is_blocked_not_green(self):
        with patch.dict(os.environ, {}, clear=True):
            payload = readiness_snapshot()
            self.assertEqual(payload["private_access"]["state"], "BLOCKED")
            self.assertEqual(payload["factory_feed"]["state"], "NOT_CONFIGURED")
            self.assertEqual(payload["business_metric_feed"]["state"], "NOT_CONFIGURED")
            self.assertEqual(payload["two_factor"]["state"], "NOT_CONNECTED")


if __name__ == "__main__":
    unittest.main()
