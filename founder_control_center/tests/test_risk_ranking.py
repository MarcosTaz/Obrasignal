import unittest
from datetime import datetime, timezone

from founder_control_center.models import CompanyManifest, Evidence, Risk
from founder_control_center.ranking import highest_value_actions, rank_company


class RiskRankingTests(unittest.TestCase):
    def _company(self, risk=None):
        return CompanyManifest(
            id="risk-ranking-company",
            name="Risk Ranking Company",
            mission="Prove risk urgency requires current authoritative evidence.",
            status="ACTIVE",
            stage="build",
            active="Advance current product work",
            wait="NONE",
            risks=[risk] if risk else [],
        )

    def test_context_seed_high_risk_does_not_claim_current_high_risk(self):
        observed = datetime.now(timezone.utc).isoformat()
        context_risk = Risk(
            "Context hypothesis",
            "HIGH",
            "strategic",
            evidence=Evidence("founder_context_seed", observed, 604800, "context_seed"),
        )
        with_context = rank_company(self._company(context_risk))
        baseline = rank_company(self._company())
        self.assertEqual(with_context.score, baseline.score)
        self.assertFalse(any("high-severity risk" in reason for reason in with_context.reasons))
        action = highest_value_actions([self._company(context_risk)])[0]
        self.assertEqual(action["urgency"], "medium")

    def test_fresh_authoritative_high_risk_increases_current_attention(self):
        observed = datetime.now(timezone.utc).isoformat()
        live_risk = Risk(
            "Live operational risk",
            "CRITICAL",
            "technical",
            evidence=Evidence("risk-system:fixture", observed, 3600, "risk_feed"),
        )
        ranked = rank_company(self._company(live_risk))
        baseline = rank_company(self._company())
        self.assertGreater(ranked.score, baseline.score)
        self.assertIn("fresh high-severity risk evidence", ranked.reasons)
        action = highest_value_actions([self._company(live_risk)])[0]
        self.assertEqual(action["urgency"], "high")

    def test_stale_authoritative_high_risk_becomes_refresh_need_not_current_claim(self):
        stale_risk = Risk(
            "Old operational risk",
            "HIGH",
            "operations",
            evidence=Evidence("risk-system:fixture", "2020-01-01T00:00:00+00:00", 60, "risk_feed"),
        )
        ranked = rank_company(self._company(stale_risk))
        self.assertIn("high-severity risk evidence stale", ranked.reasons)
        self.assertNotIn("fresh high-severity risk evidence", ranked.reasons)
        action = highest_value_actions([self._company(stale_risk)])[0]
        self.assertEqual(action["action"], "Refresh stale high-severity risk evidence before deciding")
        self.assertEqual(action["urgency"], "high")

    def test_sourceless_high_risk_remains_unknown_for_current_urgency(self):
        sourceless = Risk("Unproven risk", "CRITICAL", "technical", evidence=None)
        ranked = rank_company(self._company(sourceless))
        self.assertFalse(any("high-severity risk" in reason for reason in ranked.reasons))
        action = highest_value_actions([self._company(sourceless)])[0]
        self.assertEqual(action["urgency"], "medium")


if __name__ == "__main__":
    unittest.main()
