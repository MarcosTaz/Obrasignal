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
        self.assertEqual(body["factory"]["freshness"], "GREEN")
        after = get_company("obrasignal")
        self.assertEqual(after.active, global_active)
        factory = next(item for item in after.factories if item.name == "CI Factory Feed")
        self.assertEqual(factory.active, "Validate machine feed")
        self.assertEqual(factory.evidence.freshness_seconds, 900)
        self.assertEqual(factory.freshness.value, "GREEN")

    def test_old_factory_feed_is_rendered_stale_not_current(self):
        os.environ["FCC_FACTORY_INGEST_TOKEN"] = "factory-test-secret"
        stale_payload = dict(self.payload)
        stale_payload.update({
            "factory_name": "Stale Factory Feed",
            "observed_at": "2020-01-01T00:00:00Z",
            "freshness_seconds": 60,
        })
        response = self.client.post(
            "/api/ingest/factory-state",
            json=stale_payload,
            headers={"Authorization": "Bearer factory-test-secret"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["factory"]["freshness"], "STALE")
        api = self.client.get("/api/companies/obrasignal/factory-state").get_json()
        stale = next(item for item in api["factories"] if item["name"] == "Stale Factory Feed")
        self.assertEqual(stale["freshness"], "STALE")
        page = self.client.get("/company/obrasignal")
        self.assertIn(b"Stale Factory Feed", page.data)
        self.assertIn(b"STALE", page.data)

    def test_out_of_order_factory_feed_is_rejected(self):
        os.environ["FCC_FACTORY_INGEST_TOKEN"] = "factory-test-secret"
        headers = {"Authorization": "Bearer factory-test-secret"}
        newer = dict(self.payload)
        newer.update({
            "factory_name": "Ordered Factory Feed",
            "active": "Newest active",
            "observed_at": "2026-08-27T15:00:00Z",
            "source": "ci:newer-factory-source",
        })
        older = dict(newer)
        older.update({
            "active": "Delayed old active",
            "observed_at": "2026-08-27T14:00:00Z",
            "source": "ci:delayed-factory-source",
        })
        self.assertEqual(self.client.post("/api/ingest/factory-state", json=newer, headers=headers).status_code, 200)
        rejected = self.client.post("/api/ingest/factory-state", json=older, headers=headers)
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("out-of-order", rejected.get_json()["detail"])
        persisted = get_company("obrasignal")
        factory = next(item for item in persisted.factories if item.name == "Ordered Factory Feed")
        self.assertEqual(factory.active, "Newest active")
        self.assertEqual(factory.evidence.source, "ci:newer-factory-source")


if __name__ == "__main__":
    unittest.main()
