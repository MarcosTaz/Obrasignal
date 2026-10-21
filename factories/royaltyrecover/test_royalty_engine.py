import unittest
from datetime import date
from decimal import Decimal

from royalty_engine import (
    DeadlineState,
    FindingState,
    PeriodInput,
    RoyaltyRule,
    RoyaltyTier,
    assess_deadline,
    calculate,
)


class SyntheticPortfolioTests(unittest.TestCase):
    def net_rule(self, rate="0.05", minimum=None, review=False, **kwargs):
        return RoyaltyRule(
            rule_id="R-1",
            basis="PERCENTAGE_NET_SALES",
            rate=Decimal(rate),
            minimum_guarantee=Decimal(minimum) if minimum else None,
            source_clause="Agreement §4.2",
            requires_professional_review=review,
            **kwargs,
        )

    def test_A_correct_reporting(self):
        result = calculate(self.net_rule(), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("10000"), reported_royalty=Decimal("4500"), paid_royalty=Decimal("4500")))
        self.assertEqual(result.state, FindingState.NO_DEFENSIBLE_RECOVERY)

    def test_B_unreported_product_sales(self):
        result = calculate(self.net_rule(), PeriodInput(gross_sales=Decimal("120000"), permitted_deductions=Decimal("10000"), reported_royalty=Decimal("4500"), paid_royalty=Decimal("4500")))
        self.assertEqual(result.recoverable_candidate, Decimal("1000.00"))

    def test_C_incorrect_deduction(self):
        result = calculate(self.net_rule(), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("5000"), reported_royalty=Decimal("4000"), paid_royalty=Decimal("4000")))
        self.assertEqual(result.state, FindingState.RECOVERY_CANDIDATE)

    def test_D_wrong_royalty_rate(self):
        result = calculate(self.net_rule("0.07"), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("5000"), paid_royalty=Decimal("5000")))
        self.assertEqual(result.recoverable_candidate, Decimal("2000.00"))

    def test_E_threshold_ambiguous_fails_closed(self):
        rule = RoyaltyRule("R-E", "TIERED_RATE", source_clause="Agreement §4.3")
        self.assertEqual(calculate(rule, PeriodInput()).state, FindingState.REQUIRES_PROFESSIONAL_REVIEW)

    def test_F_sublicense_omitted(self):
        result = calculate(self.net_rule(), PeriodInput(gross_sales=Decimal("200000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("8000"), paid_royalty=Decimal("8000")))
        self.assertEqual(result.recoverable_candidate, Decimal("2000.00"))

    def test_G_territory_omitted(self):
        result = calculate(self.net_rule(), PeriodInput(gross_sales=Decimal("150000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("6000"), paid_royalty=Decimal("6000")))
        self.assertEqual(result.recoverable_candidate, Decimal("1500.00"))

    def test_H_fx_error_represented_as_supported_base_difference(self):
        rule = RoyaltyRule("R-H", "PERCENTAGE_GROSS_SALES", rate=Decimal("0.04"), source_clause="Agreement §4.4")
        result = calculate(rule, PeriodInput(gross_sales=Decimal("250000"), reported_royalty=Decimal("9500"), paid_royalty=Decimal("9500")))
        self.assertEqual(result.recoverable_candidate, Decimal("500.00"))

    def test_I_minimum_guarantee_shortfall(self):
        result = calculate(self.net_rule(rate="0.01", minimum="5000"), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("1000"), paid_royalty=Decimal("1000")))
        self.assertEqual(result.recoverable_candidate, Decimal("4000.00"))

    def test_J_bundle_allocation_ambiguity(self):
        rule = RoyaltyRule("R-J", "BUNDLE_ALLOCATION", source_clause="Agreement §4.5")
        self.assertEqual(calculate(rule, PeriodInput()).state, FindingState.REQUIRES_PROFESSIONAL_REVIEW)

    def test_K_related_party_sale_requires_review(self):
        self.assertEqual(calculate(self.net_rule(review=True), PeriodInput()).state, FindingState.REQUIRES_PROFESSIONAL_REVIEW)

    def test_L_missing_sales_data(self):
        data = PeriodInput(reported_royalty=Decimal("1000"), paid_royalty=Decimal("1000"), source_data_complete=False)
        self.assertEqual(calculate(self.net_rule(), data).state, FindingState.NEEDS_DATA)

    def test_M_amended_agreement_changes_rate(self):
        old = calculate(self.net_rule("0.05"), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("5000"), paid_royalty=Decimal("5000")))
        amended = calculate(self.net_rule("0.06"), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("5000"), paid_royalty=Decimal("5000")))
        self.assertEqual(old.state, FindingState.NO_DEFENSIBLE_RECOVERY)
        self.assertEqual(amended.recoverable_candidate, Decimal("1000.00"))

    def test_N_false_positive_trap(self):
        result = calculate(self.net_rule(), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("20000"), reported_royalty=Decimal("4000"), paid_royalty=Decimal("4000")))
        self.assertEqual(result.state, FindingState.NO_DEFENSIBLE_RECOVERY)

    def test_O_licensor_expectation_wrong(self):
        result = calculate(self.net_rule("0.03"), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("3000"), paid_royalty=Decimal("3000")))
        self.assertEqual(result.state, FindingState.NO_DEFENSIBLE_RECOVERY)

    def test_P_multiple_simultaneous_leakage_mechanisms(self):
        result = calculate(self.net_rule("0.06"), PeriodInput(gross_sales=Decimal("200000"), permitted_deductions=Decimal("5000"), reported_royalty=Decimal("9000"), paid_royalty=Decimal("8500")))
        self.assertEqual(result.recoverable_candidate, Decimal("3200.00"))

    def test_Q_lookback_deadline_approaching(self):
        self.assertEqual(assess_deadline(date(2026, 8, 29), date(2026, 9, 20)).state, DeadlineState.APPROACHING)

    def test_R_already_paid_amount_not_recovered_twice(self):
        result = calculate(self.net_rule(), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("5000"), paid_royalty=Decimal("5000")))
        self.assertEqual(result.recoverable_candidate, Decimal("0.00"))

    def test_S_duplicate_transaction_fails_closed(self):
        result = calculate(self.net_rule(), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("5000"), paid_royalty=Decimal("5000"), duplicate_transactions_detected=True))
        self.assertEqual(result.state, FindingState.NEEDS_DATA)

    def test_T_conflicting_datasets_fail_closed(self):
        result = calculate(self.net_rule(), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("5000"), paid_royalty=Decimal("5000"), conflicting_datasets=True))
        self.assertEqual(result.state, FindingState.NEEDS_DATA)

    def test_missing_clause_never_claims_money(self):
        rule = RoyaltyRule("R-X", "PERCENTAGE_GROSS_SALES", rate=Decimal("0.05"))
        result = calculate(rule, PeriodInput(gross_sales=Decimal("100000"), reported_royalty=Decimal("0"), paid_royalty=Decimal("0")))
        self.assertEqual(result.state, FindingState.UNKNOWN)
        self.assertIsNone(result.recoverable_candidate)

    def test_progressive_tiers_are_deterministic(self):
        rule = RoyaltyRule(
            "R-TIER", "TIERED_NET_SALES", source_clause="Agreement §4.6",
            tiers=(
                RoyaltyTier(Decimal("0"), Decimal("0.04"), Decimal("100000"), "§4.6(a)"),
                RoyaltyTier(Decimal("100000"), Decimal("0.06"), None, "§4.6(b)"),
            ),
        )
        result = calculate(rule, PeriodInput(gross_sales=Decimal("150000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("7000"), paid_royalty=Decimal("7000")))
        self.assertEqual(result.expected_royalty, Decimal("7000.00"))
        self.assertEqual(result.state, FindingState.NO_DEFENSIBLE_RECOVERY)

    def test_gapped_tiers_fail_closed(self):
        rule = RoyaltyRule(
            "R-GAP", "TIERED_NET_SALES", source_clause="Agreement §4.7",
            tiers=(
                RoyaltyTier(Decimal("0"), Decimal("0.04"), Decimal("100000"), "§4.7(a)"),
                RoyaltyTier(Decimal("110000"), Decimal("0.06"), None, "§4.7(b)"),
            ),
        )
        result = calculate(rule, PeriodInput(gross_sales=Decimal("150000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("0"), paid_royalty=Decimal("0")))
        self.assertEqual(result.state, FindingState.REQUIRES_PROFESSIONAL_REVIEW)

    def test_sublicense_share(self):
        rule = RoyaltyRule("R-SUB", "SUBLICENSE_SHARE", sublicense_share=Decimal("0.25"), source_clause="Agreement §5.1")
        result = calculate(rule, PeriodInput(sublicense_revenue=Decimal("40000"), reported_royalty=Decimal("8000"), paid_royalty=Decimal("8000")))
        self.assertEqual(result.recoverable_candidate, Decimal("2000.00"))

    def test_fx_requires_evidence(self):
        rule = RoyaltyRule("R-FX", "PERCENTAGE_GROSS_SALES", rate=Decimal("0.10"), currency="EUR", source_clause="Agreement §6")
        result = calculate(rule, PeriodInput(gross_sales=Decimal("10000"), source_currency="USD", fx_rate_to_rule_currency=Decimal("0.90"), reported_royalty=Decimal("900"), paid_royalty=Decimal("900")))
        self.assertEqual(result.state, FindingState.NEEDS_DATA)

    def test_fx_with_source_date_and_evidence(self):
        rule = RoyaltyRule("R-FX", "PERCENTAGE_GROSS_SALES", rate=Decimal("0.10"), currency="EUR", source_clause="Agreement §6")
        result = calculate(rule, PeriodInput(gross_sales=Decimal("10000"), source_currency="USD", fx_rate_to_rule_currency=Decimal("0.90"), fx_rate_date=date(2026, 6, 30), fx_evidence_id="ECB-2026-06-30", reported_royalty=Decimal("850"), paid_royalty=Decimal("850")))
        self.assertEqual(result.expected_royalty, Decimal("900.00"))
        self.assertEqual(result.recoverable_candidate, Decimal("50.00"))

    def test_cap_and_floor(self):
        capped = calculate(self.net_rule(rate="0.10", cap=Decimal("6000")), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("6000"), paid_royalty=Decimal("6000")))
        floored = calculate(self.net_rule(rate="0.01", floor=Decimal("3000")), PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("0"), reported_royalty=Decimal("1000"), paid_royalty=Decimal("1000")))
        self.assertEqual(capped.expected_royalty, Decimal("6000.00"))
        self.assertEqual(floored.recoverable_candidate, Decimal("2000.00"))


if __name__ == "__main__":
    unittest.main()
