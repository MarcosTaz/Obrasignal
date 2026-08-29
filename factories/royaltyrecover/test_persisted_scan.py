import unittest
from decimal import Decimal

from contract_store import ContractStore
from persisted_scan import run_persisted_scan
from repository import NotFoundError, RoyaltyRepository
from royalty_engine import FindingState, PeriodInput


class PersistedScanTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.repo.ensure_organization("ORG-A", "Alpha", "tester")
        self.repo.ensure_organization("ORG-B", "Beta", "tester")
        self.contracts = ContractStore(self.repo)
        licensor = self.repo.create_licensor("ORG-A", "Alpha University", "tester")
        licensee = self.repo.create_licensee("ORG-A", "Technology Licensee", "tester")
        self.agreement = self.repo.create_agreement("ORG-A", licensor["id"], licensee["id"], "Patent Licence", "tester")
        self.version = self.repo.add_agreement_version("ORG-A", self.agreement["id"], "v1", b"agreement-v1", "tester")
        self.contract_evidence = self.repo.add_evidence("ORG-A", "AGREEMENT", b"agreement-v1", "tester")
        self.statement_evidence = self.repo.add_evidence("ORG-A", "ROYALTY_STATEMENT", b"statement-q1", "tester")
        self.payment_evidence = self.repo.add_evidence("ORG-A", "PAYMENT", b"payment-q1", "tester")

    def tearDown(self):
        self.repo.close()

    def reviewed_rule(self, clause_status="REVIEWED", rule_status="REVIEWED"):
        clause = self.contracts.add_clause(
            "ORG-A", self.version["id"], "4.2", "ROYALTY_RATE", "tester",
            text_excerpt="Five percent of Net Sales.", evidence_id=self.contract_evidence["id"], review_status=clause_status,
        )
        rule = self.contracts.add_royalty_rule(
            "ORG-A", self.version["id"], clause["id"], "PERCENTAGE_NET_SALES", "EUR", "tester",
            rate=Decimal("0.05"), review_status=rule_status,
        )
        return clause, rule

    def period(self, gross="120000", reported="4500", paid="4500", source_complete=True):
        return PeriodInput(
            gross_sales=Decimal(gross), permitted_deductions=Decimal("10000"),
            reported_royalty=Decimal(reported), paid_royalty=Decimal(paid),
            source_data_complete=source_complete,
        )

    def test_reviewed_rule_creates_candidate_with_persistent_lineage(self):
        clause, rule = self.reviewed_rule()
        result = run_persisted_scan(
            self.repo, "ORG-A", self.agreement["id"], self.version["id"], rule["id"],
            "2026-01-01", "2026-03-31", self.period(),
            [self.statement_evidence["id"], self.payment_evidence["id"]], "tester",
        )
        self.assertEqual(result.calculation_state, FindingState.RECOVERY_CANDIDATE)
        self.assertEqual(result.recoverable_candidate, Decimal("1000.00"))
        self.assertEqual(result.finding["source_clause_id"], clause["id"])
        self.assertFalse(result.claim_ready)
        self.assertEqual(result.finding["review_status"], "PENDING")
        self.assertEqual(result.calculation_run["agreement_version_id"], self.version["id"])

    def test_correct_licensee_persists_no_defensible_recovery(self):
        _, rule = self.reviewed_rule()
        result = run_persisted_scan(
            self.repo, "ORG-A", self.agreement["id"], self.version["id"], rule["id"],
            "2026-01-01", "2026-03-31", self.period(gross="100000"),
            [self.statement_evidence["id"], self.payment_evidence["id"]], "tester",
        )
        self.assertEqual(result.calculation_state, FindingState.NO_DEFENSIBLE_RECOVERY)
        self.assertEqual(result.recoverable_candidate, Decimal("0.00"))
        self.assertFalse(result.claim_ready)

    def test_unreviewed_clause_blocks_money_calculation(self):
        _, rule = self.reviewed_rule(clause_status="UNREVIEWED")
        with self.assertRaises(ValueError):
            run_persisted_scan(
                self.repo, "ORG-A", self.agreement["id"], self.version["id"], rule["id"],
                "2026-01-01", "2026-03-31", self.period(),
                [self.statement_evidence["id"]], "tester",
            )

    def test_unreviewed_rule_blocks_money_calculation(self):
        _, rule = self.reviewed_rule(rule_status="UNREVIEWED")
        with self.assertRaises(ValueError):
            run_persisted_scan(
                self.repo, "ORG-A", self.agreement["id"], self.version["id"], rule["id"],
                "2026-01-01", "2026-03-31", self.period(),
                [self.statement_evidence["id"]], "tester",
            )

    def test_cross_tenant_evidence_is_rejected(self):
        _, rule = self.reviewed_rule()
        foreign = self.repo.add_evidence("ORG-B", "PAYMENT", b"foreign", "tester")
        with self.assertRaises(NotFoundError):
            run_persisted_scan(
                self.repo, "ORG-A", self.agreement["id"], self.version["id"], rule["id"],
                "2026-01-01", "2026-03-31", self.period(),
                [foreign["id"]], "tester",
            )

    def test_evidence_is_required_even_when_arithmetic_inputs_are_supplied(self):
        _, rule = self.reviewed_rule()
        with self.assertRaises(ValueError):
            run_persisted_scan(
                self.repo, "ORG-A", self.agreement["id"], self.version["id"], rule["id"],
                "2026-01-01", "2026-03-31", self.period(), [], "tester",
            )

    def test_input_change_marks_persisted_calculation_stale(self):
        _, rule = self.reviewed_rule()
        result = run_persisted_scan(
            self.repo, "ORG-A", self.agreement["id"], self.version["id"], rule["id"],
            "2026-01-01", "2026-03-31", self.period(),
            [self.statement_evidence["id"]], "tester",
        )
        original_hash = result.calculation_run["input_hash"]
        status = self.repo.calculation_run_freshness(
            "ORG-A", result.calculation_run["id"], self.version["id"], "0.2.0",
            {"different": "payload"},
        )
        self.assertEqual(status["status"], "STALE")
        self.assertNotEqual(status["current_input_hash"], original_hash)


if __name__ == "__main__":
    unittest.main()
