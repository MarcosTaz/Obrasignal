import unittest
from decimal import Decimal

from factories.capacity_commitment.engine import RecoveryCase, evaluate_recoverability
from factories.capacity_commitment.synthetic_cases import CASES


class RecoverabilityOracleTests(unittest.TestCase):
    def test_all_frozen_synthetic_cases(self):
        for case, expected in CASES:
            with self.subTest(case_id=case.case_id):
                result = evaluate_recoverability(case)
                self.assertEqual(result.recoverability_state, expected["state"])
                self.assertEqual(result.economic_exposure, expected["economic_exposure"])
                self.assertEqual(result.net_exposure, expected["net_exposure"])
                self.assertEqual(result.recoverable_amount, expected["recoverable"])
                self.assertEqual(result.claimable_amount, expected["recoverable"])

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
        case, _ = CASES[1]
        case = RecoveryCase(
            **{**case.__dict__, "case_id": "over-mitigated", "mitigation": Decimal("999999")}
        )
        result = evaluate_recoverability(case)
        self.assertEqual(result.net_exposure, Decimal("0"))
        self.assertEqual(result.recoverable_amount, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
