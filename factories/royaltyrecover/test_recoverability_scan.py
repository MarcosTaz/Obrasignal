import unittest
from datetime import date
from decimal import Decimal

from recoverability_scan import LicenseeSignal, ScanState, rank_portfolio, scan_licensee
from royalty_engine import DeadlineState, FindingState


TODAY = date(2026, 8, 29)


class RecoverabilityScanTests(unittest.TestCase):
    def signal(self, **kwargs):
        values = dict(
            licensee_id="L-1",
            annual_reported_royalty=Decimal("1500000"),
            finding_state=FindingState.RECOVERY_CANDIDATE,
            supported_variance=Decimal("50000"),
            audit_deadline=date(2026, 10, 1),
            audit_right_supported=True,
            source_data_complete=True,
            contract_version_complete=True,
        )
        values.update(kwargs)
        return LicenseeSignal(**values)

    def test_deadline_and_supported_variance_raise_priority(self):
        result = scan_licensee(self.signal(), TODAY)
        self.assertEqual(result.state, ScanState.READY_FOR_DESK_REVIEW)
        self.assertEqual(result.deadline_state, DeadlineState.APPROACHING)
        self.assertGreaterEqual(result.priority_score, 90)

    def test_contract_required_auditor_changes_route_not_evidence(self):
        result = scan_licensee(self.signal(auditor_requirement="Independent CPA"), TODAY)
        self.assertEqual(result.state, ScanState.FORMAL_AUDIT_CANDIDATE)
        self.assertTrue(result.formal_auditor_required)

    def test_unknown_audit_right_never_becomes_formal_audit_candidate(self):
        result = scan_licensee(self.signal(audit_right_supported=None), TODAY)
        self.assertEqual(result.state, ScanState.NEEDS_DATA)
        self.assertIn("contract-supported audit-right determination", result.missing_items)

    def test_missing_amendment_set_fails_closed(self):
        result = scan_licensee(self.signal(contract_version_complete=False), TODAY)
        self.assertEqual(result.state, ScanState.NEEDS_DATA)
        self.assertIn("complete operative agreement/amendment set", result.missing_items)

    def test_no_recovery_signal_is_valid_terminal_scan_output(self):
        result = scan_licensee(self.signal(
            finding_state=FindingState.NO_DEFENSIBLE_RECOVERY,
            supported_variance=Decimal("0"),
        ), TODAY)
        self.assertEqual(result.state, ScanState.NO_CURRENT_RECOVERY_SIGNAL)

    def test_expired_deadline_does_not_assert_right_is_lost(self):
        result = scan_licensee(self.signal(audit_deadline=date(2026, 1, 1)), TODAY)
        self.assertEqual(result.state, ScanState.PROFESSIONAL_REVIEW)
        self.assertTrue(any("not assumed lost" in reason for reason in result.rationale))

    def test_portfolio_ranking_puts_high_supported_urgency_first(self):
        high = self.signal(licensee_id="HIGH")
        low = self.signal(
            licensee_id="LOW",
            annual_reported_royalty=Decimal("100000"),
            finding_state=FindingState.NO_DEFENSIBLE_RECOVERY,
            supported_variance=Decimal("0"),
            audit_deadline=date(2027, 12, 31),
        )
        ranked = rank_portfolio([low, high], TODAY)
        self.assertEqual(ranked[0].licensee_id, "HIGH")
        self.assertGreater(ranked[0].priority_score, ranked[1].priority_score)

    def test_missing_stream_value_is_data_gap_not_fake_zero(self):
        result = scan_licensee(self.signal(annual_reported_royalty=None), TODAY)
        self.assertEqual(result.state, ScanState.NEEDS_DATA)
        self.assertIn("annual royalty stream value", result.missing_items)


if __name__ == "__main__":
    unittest.main()
