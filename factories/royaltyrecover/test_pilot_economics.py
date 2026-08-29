import unittest
from decimal import Decimal

from pilot_economics import PilotEconomicsInput, calculate_pilot_economics


class PilotEconomicsTests(unittest.TestCase):
    def test_margin_is_derived_only_from_supplied_operating_costs(self):
        result = calculate_pilot_economics(PilotEconomicsInput(
            fixed_fee_revenue=Decimal("5000"),
            analyst_minutes=600,
            reviewer_minutes=180,
            normalization_minutes=300,
            analyst_hourly_cost=Decimal("50"),
            reviewer_hourly_cost=Decimal("80"),
            normalization_hourly_cost=Decimal("40"),
            partner_direct_cost=Decimal("200"),
            hosting_direct_cost=Decimal("20"),
            agreements_received=25,
            agreements_completed=25,
            recovery_candidates=5,
            no_current_recovery=15,
            needs_data_or_review=5,
        ))
        self.assertEqual(result.direct_delivery_cost, Decimal("1160"))
        self.assertEqual(result.gross_profit, Decimal("3840"))
        self.assertEqual(result.gross_margin_ratio, Decimal("0.768"))
        self.assertTrue(result.commercial_gate_60pct_margin)
        self.assertTrue(result.zero_false_positive_gate)
        self.assertTrue(result.portfolio_scaling_evidence_available)

    def test_zero_revenue_never_fabricates_margin(self):
        result = calculate_pilot_economics(PilotEconomicsInput(
            fixed_fee_revenue=Decimal("0"), analyst_minutes=0, reviewer_minutes=0, normalization_minutes=0,
            analyst_hourly_cost=Decimal("0"), reviewer_hourly_cost=Decimal("0"), normalization_hourly_cost=Decimal("0"),
        ))
        self.assertIsNone(result.gross_margin_ratio)
        self.assertIsNone(result.direct_cost_ratio)
        self.assertFalse(result.commercial_gate_60pct_margin)

    def test_false_positive_gate_fails_when_confirmed_false_positive_exists(self):
        result = calculate_pilot_economics(PilotEconomicsInput(
            fixed_fee_revenue=Decimal("2500"), analyst_minutes=60, reviewer_minutes=30, normalization_minutes=30,
            analyst_hourly_cost=Decimal("40"), reviewer_hourly_cost=Decimal("60"), normalization_hourly_cost=Decimal("40"),
            agreements_received=10, agreements_completed=10, false_positives_confirmed=1,
        ))
        self.assertFalse(result.zero_false_positive_gate)

    def test_impossible_classification_counts_fail_closed(self):
        with self.assertRaises(ValueError):
            calculate_pilot_economics(PilotEconomicsInput(
                fixed_fee_revenue=Decimal("2500"), analyst_minutes=0, reviewer_minutes=0, normalization_minutes=0,
                analyst_hourly_cost=Decimal("0"), reviewer_hourly_cost=Decimal("0"), normalization_hourly_cost=Decimal("0"),
                agreements_received=10, agreements_completed=10, recovery_candidates=6, no_current_recovery=5,
            ))

    def test_completed_cannot_exceed_received(self):
        with self.assertRaises(ValueError):
            calculate_pilot_economics(PilotEconomicsInput(
                fixed_fee_revenue=Decimal("2500"), analyst_minutes=0, reviewer_minutes=0, normalization_minutes=0,
                analyst_hourly_cost=Decimal("0"), reviewer_hourly_cost=Decimal("0"), normalization_hourly_cost=Decimal("0"),
                agreements_received=9, agreements_completed=10,
            ))


if __name__ == "__main__":
    unittest.main()
