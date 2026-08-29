import unittest
from datetime import date
from decimal import Decimal

from recoverability_scan import ScanState
from royalty_engine import FindingState, PeriodInput, RoyaltyRule
from service_pipeline import RecoverabilityCase, pack_to_dict, run_case


TODAY = date(2026, 8, 29)


class ServicePipelineTests(unittest.TestCase):
    def case(self, **kwargs):
        values = dict(
            case_id="CASE-1",
            licensee_id="LICENSEE-1",
            agreement_id="AGR-1",
            annual_reported_royalty=Decimal("1500000"),
            audit_deadline=date(2026, 10, 1),
            audit_right_supported=True,
            contract_version_complete=True,
            auditor_requirement=None,
            rule=RoyaltyRule(
                rule_id="RULE-1",
                basis="PERCENTAGE_NET_SALES",
                rate=Decimal("0.05"),
                source_clause="Agreement §4.2",
            ),
            period_input=PeriodInput(
                gross_sales=Decimal("120000"),
                permitted_deductions=Decimal("10000"),
                reported_royalty=Decimal("4500"),
                paid_royalty=Decimal("4500"),
            ),
        )
        values.update(kwargs)
        return RecoverabilityCase(**values)

    def test_positive_variance_produces_candidate_not_claim(self):
        pack = run_case(self.case(), TODAY)
        self.assertEqual(pack.calculation.state, FindingState.RECOVERY_CANDIDATE)
        self.assertEqual(pack.calculation.recoverable_candidate, Decimal("1000.00"))
        self.assertEqual(pack.scan.state, ScanState.READY_FOR_DESK_REVIEW)
        self.assertFalse(pack.claim_ready)
        self.assertIn("review", pack.claim_blocker.lower())

    def test_formal_auditor_requirement_routes_case(self):
        pack = run_case(self.case(auditor_requirement="Independent CPA"), TODAY)
        self.assertEqual(pack.scan.state, ScanState.FORMAL_AUDIT_CANDIDATE)
        self.assertTrue(pack.scan.formal_auditor_required)
        self.assertFalse(pack.claim_ready)

    def test_missing_clause_outputs_unknown_and_information_request(self):
        rule = RoyaltyRule("RULE-X", "PERCENTAGE_GROSS_SALES", rate=Decimal("0.05"))
        pack = run_case(self.case(rule=rule), TODAY)
        self.assertEqual(pack.calculation.state, FindingState.UNKNOWN)
        self.assertEqual(pack.scan.state, ScanState.NEEDS_DATA)
        self.assertIn("operative royalty clause and source location", pack.information_requests)
        self.assertIsNone(pack.calculation.recoverable_candidate)

    def test_correct_licensee_is_not_forced_into_recovery(self):
        period = PeriodInput(
            gross_sales=Decimal("100000"),
            permitted_deductions=Decimal("10000"),
            reported_royalty=Decimal("4500"),
            paid_royalty=Decimal("4500"),
        )
        pack = run_case(self.case(period_input=period), TODAY)
        self.assertEqual(pack.calculation.state, FindingState.NO_DEFENSIBLE_RECOVERY)
        self.assertEqual(pack.scan.state, ScanState.NO_CURRENT_RECOVERY_SIGNAL)
        self.assertFalse(pack.claim_ready)

    def test_serialized_pack_preserves_decimal_as_string(self):
        packed = pack_to_dict(run_case(self.case(), TODAY))
        self.assertEqual(packed["calculation"]["recoverable_candidate"], "1000.00")
        self.assertEqual(packed["calculation"]["state"], "RECOVERY_CANDIDATE")
        self.assertFalse(packed["claim_ready"])


if __name__ == "__main__":
    unittest.main()
