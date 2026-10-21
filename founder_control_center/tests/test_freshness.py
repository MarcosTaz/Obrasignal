import unittest
from datetime import datetime, timezone

from founder_control_center.models import ApplicationState, CompanyManifest, Evidence, Metric, RepositoryState, TruthState
from founder_control_center.registry import get_company, save_company


class FreshnessTests(unittest.TestCase):
    def test_stale_evidence_invalidates_green_operational_states(self):
        old = Evidence(
            source="ci:stale-fixture",
            observed_at="2020-01-01T00:00:00+00:00",
            freshness_seconds=60,
            kind="test",
        )
        company = CompanyManifest(
            id="stale-evidence-company",
            name="Stale Evidence Company",
            mission="Prove stale evidence cannot remain green.",
            revenue=Metric("revenue", "Revenue", 100.0, "EUR", TruthState.GREEN, old),
            repository=RepositoryState("owner/repo", "main", "abc", TruthState.GREEN, old),
            application=ApplicationState(
                name="App",
                url="https://example.test",
                deployment=TruthState.GREEN,
                health=TruthState.GREEN,
                deployment_evidence=old,
                health_evidence=old,
            ),
        )
        save_company(company)
        loaded = get_company("stale-evidence-company")
        self.assertEqual(loaded.revenue.state, TruthState.STALE)
        self.assertEqual(loaded.repository.ci, TruthState.STALE)
        self.assertEqual(loaded.application.deployment, TruthState.STALE)
        self.assertEqual(loaded.application.health, TruthState.STALE)

    def test_state_without_provenance_fails_closed_to_unknown(self):
        company = CompanyManifest(
            id="missing-provenance-company",
            name="Missing Provenance Company",
            mission="Prove source metadata is mandatory for trusted operational state.",
            revenue=Metric("revenue", "Revenue", 100.0, "EUR", TruthState.GREEN, None),
            repository=RepositoryState("owner/repo", "main", "abc", TruthState.GREEN, None),
            application=ApplicationState(deployment=TruthState.GREEN, health=TruthState.GREEN),
        )
        save_company(company)
        loaded = get_company("missing-provenance-company")
        self.assertEqual(loaded.revenue.state, TruthState.UNKNOWN)
        self.assertEqual(loaded.repository.ci, TruthState.UNKNOWN)
        self.assertEqual(loaded.application.deployment, TruthState.UNKNOWN)
        self.assertEqual(loaded.application.health, TruthState.UNKNOWN)

    def test_future_dated_evidence_is_not_fresh(self):
        evidence = Evidence(
            source="ci:future-fixture",
            observed_at="2030-01-01T00:20:00+00:00",
            freshness_seconds=3600,
            kind="test",
        )
        now = datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(evidence.freshness_state(now=now), TruthState.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
