import unittest
from decimal import Decimal

from finding_store import FindingStore
from outcome_store import OutcomeStore
from repository import NotFoundError, RoyaltyRepository
from royalty_engine import FindingState


class OutcomeStoreTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.repo.ensure_organization("ORG-A", "Alpha", "system")
        self.repo.ensure_organization("ORG-B", "Beta", "system")
        licensor = self.repo.create_licensor("ORG-A", "University", "system")
        licensee = self.repo.create_licensee("ORG-A", "Licensee", "system")
        self.agreement = self.repo.create_agreement("ORG-A", licensor["id"], licensee["id"], "Patent Licence", "system")
        self.findings = FindingStore(self.repo)
        self.outcomes = OutcomeStore(self.repo)
        self.finding = self.findings.create_finding(
            "ORG-A", self.agreement["id"], "PERSISTED_RULE_SCAN", FindingState.RECOVERY_CANDIDATE,
            "SUPPORTED_DETERMINISTIC_ARITHMETIC", "analyst", amount=Decimal("1000"), currency="EUR"
        )
        self.findings.add_review("ORG-A", self.finding["id"], "reviewer", "REVIEWER", "ROUTE_TO_FORMAL_AUDIT", "external audit required")
        self.outcome_evidence = self.repo.add_evidence("ORG-A", "AUDIT_OUTCOME", b"auditor confirms adjustment", "reviewer")
        self.payment_evidence = self.repo.add_evidence("ORG-A", "PAYMENT", b"bank settlement receipt", "reviewer")

    def tearDown(self):
        self.repo.close()

    def test_recovered_amount_starts_unverified_then_requires_explicit_verification(self):
        outcome = self.outcomes.record_outcome(
            "ORG-A", self.finding["id"], "SETTLED", "reviewer", evidence_id=self.outcome_evidence["id"]
        )
        payment = self.outcomes.record_payment(
            "ORG-A", self.agreement["id"], "2026-08-29", "EUR", "1000", self.payment_evidence["id"], "reviewer", "BANK-1"
        )
        recovered = self.outcomes.record_recovered_amount_candidate(
            "ORG-A", outcome["id"], payment["id"], "1000", "EUR", self.payment_evidence["id"], "reviewer"
        )
        self.assertEqual(recovered["incremental_status"], "UNVERIFIED")
        verified = self.outcomes.verify_recovered_amount("ORG-A", recovered["id"], "reviewer", "payment and settlement evidence matched")
        self.assertEqual(verified["incremental_status"], "VERIFIED_PAYMENT")
        summary = self.outcomes.verified_summary("ORG-A")
        self.assertEqual(summary["verified_recovery_count"], 1)
        self.assertEqual(summary["verified_recovery_total"], "1000")
        self.assertEqual(summary["currency"], "EUR")

    def test_amount_cannot_exceed_evidenced_payment(self):
        outcome = self.outcomes.record_outcome("ORG-A", self.finding["id"], "SETTLED", "reviewer")
        payment = self.outcomes.record_payment("ORG-A", self.agreement["id"], "2026-08-29", "EUR", "1000", self.payment_evidence["id"], "reviewer")
        with self.assertRaises(ValueError):
            self.outcomes.record_recovered_amount_candidate(
                "ORG-A", outcome["id"], payment["id"], "1000.01", "EUR", self.payment_evidence["id"], "reviewer"
            )

    def test_no_adjustment_outcome_cannot_create_recovered_amount(self):
        outcome = self.outcomes.record_outcome("ORG-A", self.finding["id"], "NO_ADJUSTMENT", "reviewer")
        payment = self.outcomes.record_payment("ORG-A", self.agreement["id"], "2026-08-29", "EUR", "1000", self.payment_evidence["id"], "reviewer")
        with self.assertRaises(ValueError):
            self.outcomes.record_recovered_amount_candidate(
                "ORG-A", outcome["id"], payment["id"], "1000", "EUR", self.payment_evidence["id"], "reviewer"
            )

    def test_cross_tenant_payment_and_outcome_reads_fail_closed(self):
        outcome = self.outcomes.record_outcome("ORG-A", self.finding["id"], "SETTLED", "reviewer")
        payment = self.outcomes.record_payment("ORG-A", self.agreement["id"], "2026-08-29", "EUR", "1000", self.payment_evidence["id"], "reviewer")
        with self.assertRaises(NotFoundError):
            self.outcomes.get_outcome("ORG-B", outcome["id"])
        with self.assertRaises(NotFoundError):
            self.outcomes.get_payment("ORG-B", payment["id"])

    def test_mixed_currency_verified_total_is_suppressed(self):
        outcome = self.outcomes.record_outcome("ORG-A", self.finding["id"], "SETTLED", "reviewer")
        for currency, amount, ref in (("EUR", "100", "E"), ("USD", "200", "U")):
            evidence = self.repo.add_evidence("ORG-A", "PAYMENT", ref.encode(), "reviewer")
            payment = self.outcomes.record_payment("ORG-A", self.agreement["id"], "2026-08-29", currency, amount, evidence["id"], "reviewer", ref)
            recovered = self.outcomes.record_recovered_amount_candidate("ORG-A", outcome["id"], payment["id"], amount, currency, evidence["id"], "reviewer")
            self.outcomes.verify_recovered_amount("ORG-A", recovered["id"], "reviewer", "matched")
        summary = self.outcomes.verified_summary("ORG-A")
        self.assertTrue(summary["mixed_currency_total_suppressed"])
        self.assertIsNone(summary["verified_recovery_total"])


if __name__ == "__main__":
    unittest.main()
