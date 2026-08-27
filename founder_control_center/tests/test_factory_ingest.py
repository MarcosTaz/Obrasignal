import os
import unittest

from founder_control_center.app import create_app
from founder_control_center.registry import get_company


class FactoryIngestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()
        cls.payload = {
            "company_id": "obrasignal",
            "factory_name": "CI Factory Feed",
            "active": "Validate machine feed",
            "next": "Prove freshness metadata",
            "wait": "NONE",
            "source": "ci:test_factory_ingest",
            "freshness_seconds": 900,
            "material_delta": "Authenticated Factory state accepted.",
        }

    def tearDown(self):
        os.environ.pop("FCC_FACTORY_INGEST_TOKEN", None)

    def test_feed_fails_closed_when_not_configured(self):
        os.environ.pop("FCC_FACTORY_INGEST_TOKEN", None)
        response = self.client.post("/api/ingest/factory-state", json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "factory_ingest_not_configured")

    def test_feed_rejects_missing_or_wrong_bearer(self):
        os.environ["FCC_FACTORY_INGEST_TOKEN"] = "factory-test-secret"
        missing = self.client.post("/api/ingest/factory-state", json=self.payload)
        wrong = self.client.post("/api/ingest/factory-state", json=self.payload, headers={"Authorization": "Bearer wrong-secret"})
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)

    def test_valid_feed_updates_only_named_factory_state(self):
        os.environ["FCC_FACTORY_INGEST_TOKEN"] = "factory-test-secret"
        before = get_company("obrasignal")
        global_active = before.active
        response = self.client.post(
            "/api/ingest/factory-state",
            json=self.payload,
            headers={"Authorization": "Bearer factory-test-secret"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["factory"]["name"], "CI Factory Feed")
        self.assertEqual(body["factory"]["evidence"]["source"], "ci:test_factory_ingest")
        after = get_company("obrasignal")
        self.assertEqual(after.active, global_active)
        factory = next(item for item in after.factories if item.name == "CI Factory Feed")
        self.assertEqual(factory.active, "Validate machine feed")
        self.assertEqual(factory.evidence.freshness_seconds, 900)


if __name__ == "__main__":
    unittest.main()
