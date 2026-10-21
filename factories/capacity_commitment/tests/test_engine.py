import unittest
from decimal import Decimal

from factories.capacity_commitment.engine import RecoveryCase, RecoverabilityState, evaluate_recoverability
from factories.capacity_commitment.synthetic_cases import CASES, case


MANDATORY_CASE_IDS = {
    "full-volume-delivered",
    "minor-shortfall",
    "major-shortfall",
    "program-delay",
    "program-cancellation",
    "partial-cancellation",
    "no-contractual-right",
    "strong-contractual-right",
    "ambiguous-commitment",
    "forecast-only-no-firm-commitment",
    "firm-window",
    "flex-window-effective-minimum",
    "dedicated-capex",
    "shared-capex",
    "tooling-fully-amortized",
    "tooling-partially-amortized",
    "nre-already-paid",
    "unused-labor-capacity",
    "material-reused",
    "material-scrapped",
    "mitigation-partial",
    "prior-customer-credit",
    "duplicate-claim",
    "wrong-program",
    "wrong-period",
    "wrong-currency",
    "superseded-contract",
    "customer-amendment-unreconciled",
    "expired-claim-right",
    "zero-recovery-right-unknown",
}


class RecoverabilityOracleTests(unittest.TestCase):
    def test_all_frozen_synthetic_cases(self):
        for recovery_case, expected in CASES:
            with self.subTest(case_id=recovery_case.case_id):
                result = evaluate_recoverability(recovery_case)
                self.assertEqual(result.recoverability_state, expected["state"])
                self.assertEqual(result.economic_exposure, expected["economic_exposure"])
                self.assertEqual(result.net_exposure, expected["net_exposure"])
                self.assertEqual(result.recoverable_amount, expected["recoverable"])
                self.assertEqual(result.claimable_amount, expected["recoverable"])

    def test_mandatory_matrix_is_present(self):
        actual = {recovery_case.case_id for recovery_case, _ in CASES}
        self.assertTrue(MANDATORY_CASE_IDS.issubset(actual), MANDATORY_CASE_IDS - actual)
        self.assertGreaterEqual(len(CASES), len(MANDATORY_CASE_IDS))

    def test_unknown_integrity_fails_closed(self):
        recovery_case = case("unknown-integrity", program_matches=None)
        result = evaluate_recoverability(recovery_case)
        self.assertEqual(result.recoverability_state, RecoverabilityState.UNKNOWN)
        self.assertGreater(result.economic_exposure, Decimal("0"))
        self.assertEqual(result.recoverable_amount, Decimal("0"))
        self.assertEqual(result.claimable_amount, Decimal("0"))

    def test_negative_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_recoverability(
                RecoveryCase(
                    case_id="negative",
                    currency="EUR",
                    committed_units=Decimal("100"),
                    actual_units=Decimal("-1"),
                    dedicated_cost=Decimal("1000"),
                    amortization_basis_units=Decimal("100"),
                )
            )

    def test_zero_amortization_basis_is_rejected_when_cost_exists(self):
        with self.assertRaises(ValueError):
            evaluate_recoverability(
                RecoveryCase(
                    case_id="zero-basis",
                    currency="EUR",
                    committed_units=Decimal("100"),
                    actual_units=Decimal("50"),
                    dedicated_cost=Decimal("1000"),
                    amortization_basis_units=Decimal("0"),
                )
            )

    def test_mitigation_cannot_create_negative_exposure(self):
        recovery_case = case("over-mitigated", mitigation=Decimal("999999"))
        result = evaluate_recoverability(recovery_case)
        self.assertEqual(result.net_exposure, Decimal("0"))
        self.assertEqual(result.recoverable_amount, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
