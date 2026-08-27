import os
import unittest
from datetime import datetime, timedelta, timezone

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

    def _authorized_post(self, payload):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = "metric-test-secret"
        return self.client.post(
            "/api/ingest/business-metric",
            json=payload,
            headers={"Authorization": "Bearer metric-test-secret"},
        )

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
        response = self._authorized_post(self.payload)
        self.assertEqual(response.status_code, 200)
        metric = response.get_json()["metric"]
        self.assertEqual(metric["state"], "GREEN")
        self.assertEqual(metric["value"], 1250.5)
        self.assertEqual(metric["unit"], "EUR")
        self.assertEqual(metric["evidence"]["source"], "ci:canonical-billing-fixture")
        self.assertEqual(metric["evidence"]["freshness_seconds"], 900)
        persisted = get_company("founder-control-center").revenue
        self.assertEqual(persisted.state.value, "GREEN")
        self.assertEqual(persisted.value, 1250.5)

    def test_missing_source_is_rejected_instead_of_stringified(self):
        response = self._authorized_post(dict(self.payload, source=None))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_business_metric")
        self.assertIn("source is required", response.get_json()["detail"])

    def test_explicit_falsy_observed_at_cannot_be_promoted_to_now(self):
        for observed_at in ("", False, 0):
            response = self._authorized_post(dict(self.payload, observed_at=observed_at))
            self.assertEqual(response.status_code, 400)
            self.assertIn("observed_at must be ISO-8601", response.get_json()["detail"])

    def test_freshness_seconds_requires_json_integer(self):
        for freshness in (True, "900", 900.5):
            response = self._authorized_post(dict(self.payload, freshness_seconds=freshness))
            self.assertEqual(response.status_code, 400)
            self.assertIn("freshness_seconds must be an integer", response.get_json()["detail"])

    def test_detail_is_typed_and_not_silently_truncated(self):
        invalid = self._authorized_post(dict(self.payload, detail=["not", "text"]))
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("detail must be a string or null", invalid.get_json()["detail"])
        oversized = self._authorized_post(dict(self.payload, detail="D" * 1001))
        self.assertEqual(oversized.status_code, 400)
        self.assertIn("detail must be at most 1000 characters", oversized.get_json()["detail"])

    def test_null_value_cannot_be_green(self):
        payload = dict(self.payload, metric_key="pipeline", value=None, state="GREEN")
        response = self._authorized_post(payload)
        self.assertEqual(response.status_code, 200)
        metric = response.get_json()["metric"]
        self.assertEqual(metric["state"], "UNKNOWN")
        self.assertIsNone(metric["value"])

    def test_stale_first_canonical_observation_replaces_context_seed_but_not_as_green(self):
        stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        payload = dict(
            self.payload,
            company_id="black-leaf-tattoos",
            metric_key="pipeline",
            value=500,
            observed_at=stale,
            freshness_seconds=60,
            state="GREEN",
            source="ci:first-canonical-black-leaf-pipeline",
        )
        response = self._authorized_post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["metric"]["state"], "STALE")
        persisted = get_company("black-leaf-tattoos").pipeline
        self.assertEqual(persisted.state.value, "STALE")
        self.assertEqual(persisted.evidence.kind, "business_metric_feed")

    def test_canonical_business_units_cannot_be_relabelled_without_conversion(self):
        response = self._authorized_post(dict(self.payload, unit="USD"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("unit must be EUR", response.get_json()["detail"])
        customers = self._authorized_post(dict(self.payload, metric_key="customers", value=2, unit="users"))
        self.assertEqual(customers.status_code, 400)
        self.assertIn("unit must be count", customers.get_json()["detail"])

    def test_out_of_order_metric_is_rejected_without_replacing_newer_truth(self):
        now = datetime.now(timezone.utc)
        newer_at = (now - timedelta(seconds=30)).isoformat()
        older_at = (now - timedelta(seconds=90)).isoformat()
        newer = dict(
            self.payload,
            metric_key="customers",
            value=12,
            observed_at=newer_at,
            source="ci:newer-customer-source",
        )
        older = dict(
            newer,
            value=3,
            observed_at=older_at,
            source="ci:delayed-customer-source",
        )
        self.assertEqual(self._authorized_post(newer).status_code, 200)
        rejected = self._authorized_post(older)
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("out-of-order", rejected.get_json()["detail"])
        persisted = get_company("founder-control-center").customers
        self.assertEqual(persisted.value, 12)
        self.assertEqual(persisted.evidence.source, "ci:newer-customer-source")

    def test_same_observation_time_cannot_carry_two_business_truths(self):
        observed = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
        first = dict(
            self.payload,
            company_id="black-leaf-tattoos",
            metric_key="customers",
            value=7,
            observed_at=observed,
            source="ci:black-leaf-customer-source",
        )
        self.assertEqual(self._authorized_post(first).status_code, 200)
        replay = self._authorized_post(first)
        self.assertEqual(replay.status_code, 200)
        conflict = self._authorized_post(dict(first, value=8))
        self.assertEqual(conflict.status_code, 400)
        self.assertIn("identical observed_at", conflict.get_json()["detail"])
        self.assertEqual(get_company("black-leaf-tattoos").customers.value, 7)

    def test_future_dated_metric_is_rejected(self):
        payload = dict(self.payload, metric_key="pipeline", value=999, observed_at="2099-01-01T00:00:00Z")
        response = self._authorized_post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("future-dated", response.get_json()["detail"])

    def test_customers_reject_fractional_or_negative_values(self):
        for value in (-1, 1.5):
            payload = dict(self.payload, metric_key="customers", value=value)
            response = self._authorized_post(payload)
            self.assertEqual(response.status_code, 400)

    def test_unknown_metric_is_rejected(self):
        payload = dict(self.payload, metric_key="vanity_score")
        response = self._authorized_post(payload)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
