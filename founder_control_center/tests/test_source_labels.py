import json
import os
import unittest

from founder_control_center.app import create_app
from founder_control_center.registry import list_audit
from founder_control_center.security import normalize_source_label


class SourceLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()

    def tearDown(self):
        os.environ.pop("FCC_METRIC_INGEST_TOKEN", None)
        os.environ.pop("FCC_FACTORY_INGEST_TOKEN", None)

    def test_compact_provenance_labels_are_accepted(self):
        self.assertEqual(normalize_source_label("ci:billing-sync/v2"), "ci:billing-sync/v2")
        self.assertEqual(normalize_source_label("crm:hubspot"), "crm:hubspot")

    def test_url_query_and_credential_shapes_are_rejected(self):
        for value in (
            "https://example.test/feed?token=secret",
            "crm:hubspot?token=secret",
            "token=super-secret-value",
            "user@example.test",
            "ci:line\nbreak",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_source_label(value)

    def test_weak_metric_bearer_is_treated_as_not_configured(self):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = "tiny"
        response = self.client.post(
            "/api/ingest/business-metric",
            json={"company_id": "founder-control-center", "metric_key": "revenue", "value": 1, "source": "ci:test"},
            headers={"Authorization": "Bearer tiny"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "metric_ingest_not_configured")

    def test_weak_factory_bearer_is_treated_as_not_configured(self):
        os.environ["FCC_FACTORY_INGEST_TOKEN"] = "tiny"
        response = self.client.post(
            "/api/ingest/factory-state",
            json={
                "company_id": "obrasignal",
                "factory_name": "Weak Token Factory",
                "active": "Test",
                "next": "Test",
                "wait": "NONE",
                "source": "ci:test",
            },
            headers={"Authorization": "Bearer tiny"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "factory_ingest_not_configured")

    def test_business_feed_rejects_secret_like_source_without_auditing_value(self):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = "metric-test-secret"
        secret_source = "token=super-secret-value"
        response = self.client.post(
            "/api/ingest/business-metric",
            json={
                "company_id": "founder-control-center",
                "metric_key": "revenue",
                "value": 10,
                "source": secret_source,
            },
            headers={"Authorization": "Bearer metric-test-secret"},
        )
        self.assertEqual(response.status_code, 400)
        event = next(item for item in list_audit(30) if item["action"] == "business_metric" and item["result"] == "rejected_invalid_business_metric")
        serialized = json.dumps(event)
        self.assertNotIn("super-secret-value", serialized)
        self.assertNotIn(secret_source, serialized)

    def test_factory_feed_rejects_url_source_without_auditing_value(self):
        os.environ["FCC_FACTORY_INGEST_TOKEN"] = "factory-test-secret"
        unsafe_source = "https://example.test/factory?token=secret"
        response = self.client.post(
            "/api/ingest/factory-state",
            json={
                "company_id": "obrasignal",
                "factory_name": "Source Label Factory",
                "active": "Validate provenance label",
                "next": "Keep source identifiers non-secret",
                "wait": "NONE",
                "source": unsafe_source,
            },
            headers={"Authorization": "Bearer factory-test-secret"},
        )
        self.assertEqual(response.status_code, 400)
        event = next(item for item in list_audit(30) if item["action"] == "ingest_factory_state" and item["result"] == "rejected_invalid_factory_state")
        serialized = json.dumps(event)
        self.assertNotIn("token=secret", serialized)
        self.assertNotIn(unsafe_source, serialized)


if __name__ == "__main__":
    unittest.main()
