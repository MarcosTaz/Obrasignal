import unittest
from datetime import date
from decimal import Decimal

from review_workflow import HumanReview, ReviewDecision, ReviewOutcome, review_evidence_pack
from royalty_engine import FindingState, PeriodInput, RoyaltyRule
from service_pipeline import RecoverabilityCase, run_case


TODAY = date(2026, 8, 29)


class ReviewGateTests(unittest.TestCase):
    def make_pack(self, auditor_requirement=None, correct=False, incomplete=False):
        case = RecoverabilityCase(
            case_id="CASE-1",
            licensee_id="LICENSEE-1",
            agreement_id="AGR-1",
            annual_reported_royalty=Decimal("1500000"),
            audit_deadline=date(2026, 10, 1),
            audit_right_supported=True,
            contract_version_complete=True,
            auditor_requirement=auditor_requirement,
            rule=RoyaltyRule("RULE-1", "PERCENTAGE_NET_SALES", rate=Decimal("0.05"), source_clause="Agreement section 4.2"),
            period_input=PeriodInput(
                gross_sales=Decimal("100000" if correct else "120000"),
                permitted_deductions=Decimal("10000"),
                reported_royalty=Decimal("4500"),
                paid_royalty=Decimal("4500"),
                source_data_complete=not incomplete,
            ),
        )
        return run_case(case, TODAY)

    def review(self, decision):
        return HumanReview("reviewer-1", "Royalty Analyst", decision, "Reviewed source material and calculation lineage.")

    def test_positive_candidate_stays_non_assertive_after_desk_review(self):
        result = review_evidence_pack(self.make_pack(), self.review(ReviewDecision.APPROVE_DESK_FINDING))
        self.assertEqual(result.outcome, ReviewOutcome.DESK_FINDING_APPROVED)
        self.assertFalse(result.claim_ready)

    def test_formal_auditor_requirement_blocks_desk_substitution(self):
        result = review_evidence_pack(self.make_pack(auditor_requirement="Independent CPA"), self.review(ReviewDecision.APPROVE_DESK_FINDING))
        self.assertEqual(result.outcome, ReviewOutcome.BLOCKED)
        self.assertFalse(result.claim_ready)

    def test_formal_audit_routing_does_not_create_assertion(self):
        result = review_evidence_pack(self.make_pack(auditor_requirement="Independent CPA"), self.review(ReviewDecision.ROUTE_TO_FORMAL_AUDIT))
        self.assertEqual(result.outcome, ReviewOutcome.FORMAL_AUDIT_READY)
        self.assertTrue(result.formal_audit_ready)
        self.assertFalse(result.claim_ready)

    def test_correct_reporting_cannot_be_approved_as_recovery(self):
        pack = self.make_pack(correct=True)
        self.assertEqual(pack.calculation.state, FindingState.NO_DEFENSIBLE_RECOVERY)
        result = review_evidence_pack(pack, self.review(ReviewDecision.APPROVE_DESK_FINDING))
        self.assertEqual(result.outcome, ReviewOutcome.BLOCKED)

    def test_missing_data_blocks_audit_routing(self):
        result = review_evidence_pack(self.make_pack(incomplete=True), self.review(ReviewDecision.ROUTE_TO_FORMAL_AUDIT))
        self.assertEqual(result.outcome, ReviewOutcome.BLOCKED)
        self.assertFalse(result.formal_audit_ready)

    def test_reviewer_may_reject_candidate(self):
        result = review_evidence_pack(self.make_pack(), self.review(ReviewDecision.REJECT_RECOVERY))
        self.assertEqual(result.outcome, ReviewOutcome.NO_RECOVERY)

    def test_reviewer_identity_and_rationale_are_required(self):
        invalid = HumanReview("", "Royalty Analyst", ReviewDecision.APPROVE_DESK_FINDING, "")
        with self.assertRaises(ValueError):
            review_evidence_pack(self.make_pack(), invalid)


if __name__ == "__main__":
    unittest.main()
