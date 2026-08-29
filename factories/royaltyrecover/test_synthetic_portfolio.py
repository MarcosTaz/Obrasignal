import unittest
from datetime import date

from recoverability_scan import ScanState
from royalty_engine import FindingState
from synthetic_portfolio import generate_tto_portfolio, run_tto_portfolio


TODAY = date(2026, 8, 29)


class SyntheticTTOPortfolioTests(unittest.TestCase):
    def setUp(self):
        self.cases = generate_tto_portfolio(TODAY)
        self.run = run_tto_portfolio(TODAY, self.cases)

    def test_portfolio_matches_publicly_observed_scale(self):
        self.assertEqual(len(self.cases), 170)
        self.assertEqual(len(self.run.packs), 170)

    def test_clean_controls_never_become_recovery_candidates(self):
        clean = self.run.packs[:100]
        self.assertTrue(all(pack.calculation.state == FindingState.NO_DEFENSIBLE_RECOVERY for pack in clean))
        self.assertTrue(all(pack.calculation.recoverable_candidate == 0 for pack in clean))

    def test_supported_candidate_population_is_exact(self):
        self.assertEqual(self.run.count_calculation_state(FindingState.RECOVERY_CANDIDATE), 45)
        supported = [pack for pack in self.run.packs if pack.calculation.state == FindingState.RECOVERY_CANDIDATE]
        self.assertTrue(all(pack.calculation.recoverable_candidate == 1000 for pack in supported))

    def test_missing_and_duplicate_data_never_create_money_candidate(self):
        unresolved = self.run.packs[130:160]
        self.assertTrue(all(pack.calculation.recoverable_candidate is None for pack in unresolved))

    def test_professional_judgment_cases_are_explicit(self):
        self.assertEqual(self.run.count_calculation_state(FindingState.REQUIRES_PROFESSIONAL_REVIEW), 5)

    def test_formal_auditor_cases_route_without_claiming(self):
        self.assertEqual(self.run.count_scan_state(ScanState.FORMAL_AUDIT_CANDIDATE), 10)
        formal = [pack for pack in self.run.packs if pack.scan.state == ScanState.FORMAL_AUDIT_CANDIDATE]
        self.assertTrue(all(pack.scan.formal_auditor_required for pack in formal))
        self.assertTrue(all(not pack.claim_ready for pack in formal))

    def test_unknown_audit_right_blocks_audit_entitlement_assumption(self):
        unknown_right = self.run.packs[165:170]
        self.assertTrue(all(pack.scan.state == ScanState.NEEDS_DATA for pack in unknown_right))
        self.assertTrue(all("contract-supported audit-right determination" in pack.information_requests for pack in unknown_right))

    def test_no_synthetic_case_is_automatically_claim_ready(self):
        self.assertEqual(self.run.claimed_cases, 0)


if __name__ == "__main__":
    unittest.main()
