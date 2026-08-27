import os
import unittest
from datetime import datetime, timedelta, timezone

from founder_control_center.app import create_app
from founder_control_center.registry import get_company
from founder_control_center.sources import source_summary


class OperationalMetricFeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()

    def tearDown(self):
        os.environ.pop("FCC_METRIC_INGEST_TOKEN", None)

    def _post(self, payload, token="metric-test-secret"):
        os.environ["FCC_METRIC_INGEST_TOKEN"] = token
        return self.client.post(
            "/api/ingest/metric",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    def test_feed_fails_closed_without_metric_token(self):
        os.environ.pop("FCC_METRIC_INGEST_TOKEN", None)
        response = self.client.post("/api/ingest/metric", json={})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "metric_ingest_not_configured")

    def test_non_object_body_is_rejected_without_server_error(self):
        response = self._post(["bad", "shape"])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_operational_metric")

    def test_custom_metric_persists_without_overwriting_business_metrics(self):
        before = get_company("founder-control-center")
        revenue_before = before.revenue.value
        payload = {
            "company_id": "founder-control-center",
            "metric_key": "source_coverage",
            "label": "Source coverage",
            "value": 62.5,
            "unit": "%",
            "source": "ci:source-coverage-fixture",
            "freshness_seconds": 900,
            "state": "GREEN",
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        metric = response.get_json()["metric"]
        self.assertEqual(metric["key"], "source_coverage")
        self.assertEqual(metric["value"], 62.5)
        self.assertEqual(metric["evidence"]["kind"], "operational_metric_feed")
        company = get_company("founder-control-center")
        persisted = next(item for item in company.metrics if item.key == "source_coverage")
        self.assertEqual(persisted.state.value, "GREEN")
        self.assertEqual(company.revenue.value, revenue_before)
        summary = source_summary(company)
        source = next(item for item in summary["sources"] if item["label"] == "Source coverage")
        self.assertEqual(source["kind"], "operational_metric_feed")
        page = self.client.get("/company/founder-control-center")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Source-owned KPIs", page.data)
        self.assertIn(b"Source coverage", page.data)
        self.assertIn(b"62.5", page.data)

    def test_reserved_business_metric_cannot_be_shadowed(self):
        response = self._post({
            "company_id": "founder-control-center",
            "metric_key": "revenue",
            "label": "Fake revenue",
            "value": 999999,
            "source": "ci:invalid-shadow",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_operational_metric")

    def test_missing_source_is_rejected_instead_of_stringified(self):
        response = self._post({
            "company_id": "founder-control-center",
            "metric_key": "evidence_gap",
            "label": "Evidence gap",
            "value": 1,
            "source": None,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_operational_metric")

    def test_null_custom_metric_is_unknown(self):
        response = self._post({
            "company_id": "founder-control-center",
            "metric_key": "retention_signal",
            "label": "Retention signal",
            "value": None,
            "source": "ci:null-kpi",
            "state": "GREEN",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["metric"]["state"], "UNKNOWN")

    def test_delayed_custom_metric_cannot_replace_newer_observation(self):
        now = datetime.now(timezone.utc)
        newer = (now - timedelta(seconds=30)).isoformat()
        older = (now - timedelta(seconds=90)).isoformat()
        base = {
            "company_id": "founder-control-center",
            "metric_key": "activation_rate",
            "label": "Activation rate",
            "unit": "%",
            "source": "ci:ordered-kpi",
        }
        first = self._post(dict(base, value=42.0, observed_at=newer))
        self.assertEqual(first.status_code, 200)
        delayed = self._post(dict(base, value=1.0, observed_at=older))
        self.assertEqual(delayed.status_code, 400)
        persisted = next(item for item in get_company("founder-control-center").metrics if item.key == "activation_rate")
        self.assertEqual(persisted.value, 42.0)


if __name__ == "__main__":
    unittest.main()
