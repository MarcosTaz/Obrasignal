import unittest
from datetime import datetime, timezone

from founder_control_center.app import create_app
from founder_control_center.models import CompanyManifest, Evidence, FactoryState, Metric, TruthState
from founder_control_center.registry import save_company
from founder_control_center.sources import source_summary


class SourceInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()

    def test_context_seed_is_not_counted_as_live_feed(self):
        company = CompanyManifest(
            id="source-context-company",
            name="Source Context Company",
            mission="Prove context is not a live operational source.",
            revenue=Metric(
                "revenue",
                "Revenue",
                None,
                "EUR",
                TruthState.UNKNOWN,
                Evidence("founder_context_seed", "2026-08-27T15:00:00+00:00", 604800, "context_seed"),
            ),
        )
        summary = source_summary(company)
        revenue = next(item for item in summary["sources"] if item["label"] == "Revenue")
        self.assertEqual(revenue["kind"], "context_seed")
        self.assertEqual(summary["connected_source_count"], 0)
        self.assertEqual(summary["connected_boundary_count"], 0)
        self.assertEqual(summary["fresh_live_source_count"], 0)
        self.assertEqual(summary["fresh_live_boundary_count"], 0)
        self.assertEqual(summary["live_source_count"], 0)

    def test_repeated_source_label_counts_once_but_each_boundary_remains_visible(self):
        observed = datetime.now(timezone.utc).isoformat()
        source = "crm:canonical-portfolio"
        company = CompanyManifest(
            id="source-dedup-company",
            name="Source Dedup Company",
            mission="Separate source identity from evidence-boundary count.",
            revenue=Metric("revenue", "Revenue", 100, "EUR", TruthState.GREEN, Evidence(source, observed, 3600, "business_metric_feed")),
            pipeline=Metric("pipeline", "Pipeline", 250, "EUR", TruthState.GREEN, Evidence(source, observed, 3600, "business_metric_feed")),
        )
        summary = source_summary(company)
        self.assertEqual(summary["connected_source_count"], 1)
        self.assertEqual(summary["fresh_live_source_count"], 1)
        self.assertEqual(summary["connected_boundary_count"], 2)
        self.assertEqual(summary["fresh_live_boundary_count"], 2)
        self.assertEqual(len([item for item in summary["sources"] if item["source"] == source]), 2)

    def test_stale_feed_is_connected_but_not_fresh_live_truth(self):
        company = CompanyManifest(
            id="source-live-company",
            name="Source Live Company",
            mission="Expose live source provenance.",
            factories=[
                FactoryState(
                    name="Source Factory",
                    active="Run",
                    next="Continue",
                    wait="NONE",
                    evidence=Evidence("ci:source-feed", "2020-01-01T00:00:00+00:00", 60, "factory_feed"),
                )
            ],
        )
        save_company(company)
        response = self.client.get("/api/companies/source-live-company/sources")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        factory = next(item for item in payload["sources"] if item["label"] == "Factory: Source Factory")
        self.assertEqual(factory["freshness"], "STALE")
        self.assertEqual(factory["source"], "ci:source-feed")
        self.assertEqual(payload["connected_source_count"], 1)
        self.assertEqual(payload["connected_boundary_count"], 1)
        self.assertEqual(payload["fresh_live_source_count"], 0)
        self.assertEqual(payload["fresh_live_boundary_count"], 0)
        self.assertEqual(payload["live_source_count"], 0)
        page = self.client.get("/company/source-live-company")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Source inventory", page.data)
        self.assertIn(b"ci:source-feed", page.data)
        self.assertIn(b"1 connected source label(s); 0 currently fresh source label(s) across 1 connected", page.data)


if __name__ == "__main__":
    unittest.main()
