import unittest
from decimal import Decimal

from auditor_handoff import build_formal_audit_packet, packet_to_dict
from contract_store import ContractStore
from finding_store import FindingStore
from persisted_scan import run_persisted_scan
from repository import NotFoundError, RoyaltyRepository
from royalty_engine import PeriodInput


class AuditorHandoffTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.repo.ensure_organization("ORG-A", "Alpha", "system")
        self.repo.ensure_organization("ORG-B", "Beta", "system")
        licensor = self.repo.create_licensor("ORG-A", "University", "system")
        licensee = self.repo.create_licensee("ORG-A", "Licensee", "system")
        self.agreement = self.repo.create_agreement("ORG-A", licensor["id"], licensee["id"], "Patent Licence", "system")
        self.version = self.repo.add_agreement_version("ORG-A", self.agreement["id"], "v1", b"agreement", "system")
        contract_evidence = self.repo.add_evidence("ORG-A", "AGREEMENT", b"5% net sales", "system")
        self.statement_evidence = self.repo.add_evidence("ORG-A", "ROYALTY_STATEMENT", b"statement", "system")
        contracts = ContractStore(self.repo)
        clause = contracts.add_clause(
            "ORG-A", self.version["id"], "4.2", "ROYALTY_RATE", "analyst",
            text_excerpt="5% of Net Sales", evidence_id=contract_evidence["id"]
        )
        contracts.set_clause_review_status("ORG-A", clause["id"], "REVIEWED", "reviewer", "checked source")
        rule = contracts.add_royalty_rule(
            "ORG-A", self.version["id"], clause["id"], "PERCENTAGE_NET_SALES", "EUR", "analyst", rate=Decimal("0.05")
        )
        contracts.set_rule_review_status("ORG-A", rule["id"], "REVIEWED", "reviewer", "checked calculation rule")
        self.rule = rule
        self.findings = FindingStore(self.repo)

    def tearDown(self):
        self.repo.close()

    def candidate(self):
        result = run_persisted_scan(
            self.repo, "ORG-A", self.agreement["id"], self.version["id"], self.rule["id"],
            "2026-01-01", "2026-03-31",
            PeriodInput(gross_sales=Decimal("120000"), permitted_deductions=Decimal("10000"), reported_royalty=Decimal("4500"), paid_royalty=Decimal("4500")),
            [self.statement_evidence["id"]], "analyst",
        )
        return result.finding

    def test_candidate_must_be_explicitly_routed_before_packet(self):
        finding = self.candidate()
        with self.assertRaises(ValueError):
            build_formal_audit_packet(self.repo, "ORG-A", finding["id"])

    def test_reviewed_route_builds_non_claiming_evidence_bound_packet(self):
        finding = self.candidate()
        self.findings.add_review("ORG-A", finding["id"], "reviewer", "REVIEWER", "ROUTE_TO_FORMAL_AUDIT", "formal books review required")
        packet = packet_to_dict(build_formal_audit_packet(self.repo, "ORG-A", finding["id"]))
        self.assertEqual(packet["analytical_candidate_amount"], "1000.00")
        self.assertEqual(packet["review_status"], "FORMAL_AUDIT_ROUTE")
        self.assertEqual(len(packet["evidence"]), 1)
        self.assertEqual(packet["evidence"][0]["id"], self.statement_evidence["id"])
        self.assertFalse(packet["auditor_engaged"])
        self.assertFalse(packet["claim_ready"])
        self.assertIn("does not assert", packet["disclaimer"])

    def test_cross_tenant_packet_read_is_not_found(self):
        finding = self.candidate()
        self.findings.add_review("ORG-A", finding["id"], "reviewer", "REVIEWER", "ROUTE_TO_FORMAL_AUDIT", "route")
        with self.assertRaises(NotFoundError):
            build_formal_audit_packet(self.repo, "ORG-B", finding["id"])

    def test_no_recovery_finding_cannot_be_routed(self):
        result = run_persisted_scan(
            self.repo, "ORG-A", self.agreement["id"], self.version["id"], self.rule["id"],
            "2026-04-01", "2026-06-30",
            PeriodInput(gross_sales=Decimal("100000"), permitted_deductions=Decimal("10000"), reported_royalty=Decimal("4500"), paid_royalty=Decimal("4500")),
            [self.statement_evidence["id"]], "analyst",
        )
        with self.assertRaises(ValueError):
            self.findings.add_review("ORG-A", result.finding["id"], "reviewer", "REVIEWER", "ROUTE_TO_FORMAL_AUDIT", "should fail")


if __name__ == "__main__":
    unittest.main()
