import os
import unittest

from founder_control_center.app import create_app
from founder_control_center.registry import get_company


class BusinessMetricFeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()
        cls.payload = {
            "company_id": "founder-control-center",
            "metric_key": "revenue",
            "value": 1250.5,
            "source": "ci:canonical-billing-fixture",
            "freshness_seconds": 900,
            "state": "GREEN",
        }

    def tearDown(self):
        os.environ.pop("FCC_METRIC_INGEST_TOKEN", None)

    def test_feed_fails_closed_when_not_configured(self):
        os.environ.pop("FCC_METRIC_INGEST_TOKEN", None)
        response = self.client.post("/api/ingest/business-metric", json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "metric_ingest_not_configured")

    def test_feed_rejects_wrong_bearer(self):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = "metric-test-secret"
        response = self.client.post(
            "/api/ingest/business-metric",
            json=self.payload,
            headers={"Authorization": "Bearer wrong-secret"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "metric_ingest_authentication_required")

    def test_valid_feed_persists_value_source_and_freshness(self):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = "metric-test-secret"
        response = self.client.post(
            "/api/ingest/business-metric",
            json=self.payload,
            headers={"Authorization": "Bearer metric-test-secret"},
        )
        self.assertEqual(response.status_code, 200)
        metric = response.get_json()["metric"]
        self.assertEqual(metric["state"], "GREEN")
        self.assertEqual(metric["value"], 1250.5)
        self.assertEqual(metric["evidence"]["source"], "ci:canonical-billing-fixture")
        self.assertEqual(metric["evidence"]["freshness_seconds"], 900)
        persisted = get_company("founder-control-center").revenue
        self.assertEqual(persisted.state.value, "GREEN")
        self.assertEqual(persisted.value, 1250.5)

    def test_null_value_cannot_be_green(self):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = "metric-test-secret"
        payload = dict(self.payload, metric_key="pipeline", value=None, state="GREEN")
        response = self.client.post(
            "/api/ingest/business-metric",
            json=payload,
            headers={"Authorization": "Bearer metric-test-secret"},
        )
        self.assertEqual(response.status_code, 200)
        metric = response.get_json()["metric"]
        self.assertEqual(metric["state"], "UNKNOWN")
        self.assertIsNone(metric["value"])

    def test_out_of_order_metric_is_rejected_without_replacing_newer_truth(self):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = "metric-test-secret"
        headers = {"Authorization": "Bearer metric-test-secret"}
        newer = dict(
            self.payload,
            metric_key="customers",
            value=12,
            observed_at="2026-08-27T15:00:00Z",
            source="ci:newer-customer-source",
        )
        older = dict(
            newer,
            value=3,
            observed_at="2026-08-27T14:00:00Z",
            source="ci:delayed-customer-source",
        )
        self.assertEqual(self.client.post("/api/ingest/business-metric", json=newer, headers=headers).status_code, 200)
        rejected = self.client.post("/api/ingest/business-metric", json=older, headers=headers)
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("out-of-order", rejected.get_json()["detail"])
        persisted = get_company("founder-control-center").customers
        self.assertEqual(persisted.value, 12)
        self.assertEqual(persisted.evidence.source, "ci:newer-customer-source")

    def test_future_dated_metric_is_rejected(self):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = "metric-test-secret"
        payload = dict(self.payload, metric_key="pipeline", value=999, observed_at="2099-01-01T00:00:00Z")
        response = self.client.post(
            "/api/ingest/business-metric",
            json=payload,
            headers={"Authorization": "Bearer metric-test-secret"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("future-dated", response.get_json()["detail"])

    def test_customers_reject_fractional_or_negative_values(self):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = "metric-test-secret"
        for value in (-1, 1.5):
            payload = dict(self.payload, metric_key="customers", value=value)
            response = self.client.post(
                "/api/ingest/business-metric",
                json=payload,
                headers={"Authorization": "Bearer metric-test-secret"},
            )
            self.assertEqual(response.status_code, 400)

    def test_unknown_metric_is_rejected(self):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = "metric-test-secret"
        payload = dict(self.payload, metric_key="vanity_score")
        response = self.client.post(
            "/api/ingest/business-metric",
            json=payload,
            headers={"Authorization": "Bearer metric-test-secret"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
