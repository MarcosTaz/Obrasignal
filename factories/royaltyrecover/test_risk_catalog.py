import unittest
from datetime import date
from decimal import Decimal

from recoverability_scan import LicenseeSignal, scan_licensee
from risk_catalog import UC_2023_SOURCE, validate_risk_factors
from royalty_engine import FindingState


class RiskCatalogTests(unittest.TestCase):
    def signal(self, risk_factors=()):
        return LicenseeSignal(
            licensee_id="L-1",
            annual_reported_royalty=Decimal("1000000"),
            finding_state=FindingState.RECOVERY_CANDIDATE,
            supported_variance=Decimal("1000"),
            audit_deadline=date(2026, 10, 1),
            audit_right_supported=True,
            source_data_complete=True,
            contract_version_complete=True,
            risk_factors=tuple(risk_factors),
        )

    def test_known_factors_are_canonicalized_and_deduplicated(self):
        factors = validate_risk_factors(["deductions", "DEDUCTIONS", "sublicensing"])
        self.assertEqual(factors, ("DEDUCTIONS", "SUBLICENSING"))

    def test_unknown_factor_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_risk_factors(["MADE_UP_RISK"])

    def test_risk_factors_are_exposed_with_source(self):
        result = scan_licensee(self.signal(["DEDUCTIONS", "SUBLICENSING"]), date(2026, 8, 29))
        self.assertEqual(result.unweighted_risk_factors, ("DEDUCTIONS", "SUBLICENSING"))
        self.assertEqual(result.risk_factor_source, UC_2023_SOURCE)

    def test_risk_factors_do_not_change_numeric_priority_without_calibration(self):
        baseline = scan_licensee(self.signal(), date(2026, 8, 29))
        flagged = scan_licensee(self.signal(["DEDUCTIONS", "SUBLICENSING", "BUSINESS_COMBINATION"]), date(2026, 8, 29))
        self.assertEqual(flagged.priority_score, baseline.priority_score)
        self.assertTrue(any("unweighted" in reason for reason in flagged.rationale))


if __name__ == "__main__":
    unittest.main()
