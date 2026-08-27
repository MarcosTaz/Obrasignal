import unittest

from founder_control_center.models import CompanyManifest, Evidence, FactoryState, TruthState
from founder_control_center.ranking import highest_value_actions, rank_company


class FactoryRankingTests(unittest.TestCase):
    def test_stale_factory_feed_increases_attention_and_refresh_action(self):
        company = CompanyManifest(
            id="stale-feed-company",
            name="Stale Feed Company",
            mission="Test stale Factory evidence semantics.",
            status="ACTIVE",
            stage="build",
            factories=[
                FactoryState(
                    name="Live Factory",
                    active="Old task",
                    next="Old next",
                    wait="NONE",
                    evidence=Evidence(
                        source="ci:factory",
                        observed_at="2020-01-01T00:00:00+00:00",
                        freshness_seconds=60,
                        kind="factory_feed",
                    ),
                    freshness=TruthState.STALE,
                )
            ],
        )
        rank = rank_company(company)
        self.assertIn("Factory feed evidence stale", rank.reasons)
        action = highest_value_actions([company])[0]
        self.assertEqual(action["action"], "Refresh stale Factory feed before portfolio decisions")
        self.assertEqual(action["urgency"], "high")

    def test_context_seed_is_not_misrepresented_as_live_factory_feed(self):
        company = CompanyManifest(
            id="context-only-company",
            name="Context Only",
            mission="Context is not a live Factory feed.",
            status="ACTIVE",
            stage="build",
            factories=[
                FactoryState(
                    name="Context Factory",
                    active="Seeded active",
                    next="Seeded next",
                    wait="NONE",
                    evidence=Evidence(
                        source="founder_context_seed",
                        observed_at="2026-08-27T12:00:00+00:00",
                        freshness_seconds=604800,
                        kind="context_seed",
                    ),
                    freshness=TruthState.GREEN,
                )
            ],
        )
        rank = rank_company(company)
        self.assertNotIn("live Factory feed evidence available", rank.reasons)


if __name__ == "__main__":
    unittest.main()
