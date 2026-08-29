import unittest
from decimal import Decimal

from contract_store import ContractStore
from repository import NotFoundError, RoyaltyRepository


class ContractStoreTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.repo.ensure_organization("ORG-A", "Alpha", "tester")
        self.repo.ensure_organization("ORG-B", "Beta", "tester")
        self.store = ContractStore(self.repo)
        self.versions = {}
        for org_id in ("ORG-A", "ORG-B"):
            licensor = self.repo.create_licensor(org_id, f"{org_id} Licensor", "tester")
            licensee = self.repo.create_licensee(org_id, f"{org_id} Licensee", "tester")
            agreement = self.repo.create_agreement(org_id, licensor["id"], licensee["id"], "Patent Licence", "tester")
            self.versions[org_id] = self.repo.add_agreement_version(org_id, agreement["id"], "v1", b"agreement", "tester")

    def tearDown(self):
        self.repo.close()

    def test_clause_is_version_and_tenant_scoped(self):
        evidence = self.repo.add_evidence("ORG-A", "AGREEMENT", b"source", "tester")
        clause = self.store.add_clause(
            "ORG-A", self.versions["ORG-A"]["id"], "4.2", "ROYALTY_RATE", "tester",
            text_excerpt="Five percent of Net Sales.", evidence_id=evidence["id"]
        )
        self.assertEqual(clause["agreement_version_id"], self.versions["ORG-A"]["id"])
        self.assertEqual(clause["evidence_id"], evidence["id"])
        self.assertEqual(clause["review_status"], "UNREVIEWED")
        with self.assertRaises(NotFoundError):
            self.store.get_clause("ORG-B", clause["id"])

    def test_creation_cannot_self_assert_reviewed_status(self):
        with self.assertRaises(ValueError):
            self.store.add_clause(
                "ORG-A", self.versions["ORG-A"]["id"], "4.2", "ROYALTY_RATE", "tester", review_status="REVIEWED"
            )
        clause = self.store.add_clause("ORG-A", self.versions["ORG-A"]["id"], "4.2", "ROYALTY_RATE", "tester")
        with self.assertRaises(ValueError):
            self.store.add_royalty_rule(
                "ORG-A", self.versions["ORG-A"]["id"], clause["id"], "PERCENTAGE_NET_SALES", "EUR", "tester",
                rate=Decimal("0.05"), review_status="REVIEWED"
            )

    def test_cross_tenant_evidence_cannot_back_clause(self):
        evidence_b = self.repo.add_evidence("ORG-B", "AGREEMENT", b"other", "tester")
        with self.assertRaises(NotFoundError):
            self.store.add_clause(
                "ORG-A", self.versions["ORG-A"]["id"], "4.2", "ROYALTY_RATE", "tester",
                evidence_id=evidence_b["id"]
            )

    def test_percentage_rule_requires_sourced_clause_and_rate(self):
        clause = self.store.add_clause("ORG-A", self.versions["ORG-A"]["id"], "4.2", "ROYALTY_RATE", "tester")
        with self.assertRaises(ValueError):
            self.store.add_royalty_rule(
                "ORG-A", self.versions["ORG-A"]["id"], clause["id"],
                "PERCENTAGE_NET_SALES", "EUR", "tester"
            )
        rule = self.store.add_royalty_rule(
            "ORG-A", self.versions["ORG-A"]["id"], clause["id"],
            "PERCENTAGE_NET_SALES", "EUR", "tester", rate=Decimal("0.05")
        )
        self.assertEqual(rule["rate_decimal"], "0.05")
        self.assertEqual(rule["clause_id"], clause["id"])
        self.assertEqual(rule["review_status"], "UNREVIEWED")

    def test_clause_from_other_version_is_rejected(self):
        clause_b = self.store.add_clause("ORG-B", self.versions["ORG-B"]["id"], "4.2", "ROYALTY_RATE", "tester")
        with self.assertRaises(NotFoundError):
            self.store.add_royalty_rule(
                "ORG-A", self.versions["ORG-A"]["id"], clause_b["id"],
                "PERCENTAGE_NET_SALES", "EUR", "tester", rate=Decimal("0.05")
            )

    def test_cap_cannot_be_below_floor(self):
        clause = self.store.add_clause("ORG-A", self.versions["ORG-A"]["id"], "4.2", "ROYALTY_RATE", "tester")
        with self.assertRaises(ValueError):
            self.store.add_royalty_rule(
                "ORG-A", self.versions["ORG-A"]["id"], clause["id"],
                "PERCENTAGE_NET_SALES", "EUR", "tester",
                rate=Decimal("0.05"), floor=Decimal("5000"), cap=Decimal("1000")
            )

    def test_rule_read_is_tenant_scoped(self):
        clause = self.store.add_clause("ORG-A", self.versions["ORG-A"]["id"], "4.2", "ROYALTY_RATE", "tester")
        rule = self.store.add_royalty_rule(
            "ORG-A", self.versions["ORG-A"]["id"], clause["id"],
            "PERCENTAGE_NET_SALES", "EUR", "tester", rate=Decimal("0.05")
        )
        with self.assertRaises(NotFoundError):
            self.store.get_royalty_rule("ORG-B", rule["id"])

    def test_excerpt_size_is_bounded(self):
        with self.assertRaises(ValueError):
            self.store.add_clause(
                "ORG-A", self.versions["ORG-A"]["id"], "4.2", "ROYALTY_RATE", "tester",
                text_excerpt="x" * 2001
            )


if __name__ == "__main__":
    unittest.main()
