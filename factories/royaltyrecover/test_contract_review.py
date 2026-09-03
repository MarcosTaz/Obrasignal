import unittest
from decimal import Decimal

from contract_store import ContractStore
from repository import RoyaltyRepository


class ContractReviewTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.repo.ensure_organization("ORG-1", "One", "system")
        licensor = self.repo.create_licensor("ORG-1", "Licensor", "system")
        licensee = self.repo.create_licensee("ORG-1", "Licensee", "system")
        agreement = self.repo.create_agreement("ORG-1", licensor["id"], licensee["id"], "Licence", "system")
        version = self.repo.add_agreement_version("ORG-1", agreement["id"], "v1", b"contract", "system")
        evidence = self.repo.add_evidence("ORG-1", "AGREEMENT", b"clause evidence", "system")
        self.store = ContractStore(self.repo)
        self.clause = self.store.add_clause(
            "ORG-1", version["id"], "4.2", "ROYALTY", "analyst",
            text_excerpt="5% of net sales", evidence_id=evidence["id"]
        )
        self.version_id = version["id"]

    def tearDown(self):
        self.repo.close()

    def test_clause_review_requires_rationale_and_is_audited(self):
        with self.assertRaises(ValueError):
            self.store.set_clause_review_status("ORG-1", self.clause["id"], "REVIEWED", "reviewer", "")
        reviewed = self.store.set_clause_review_status("ORG-1", self.clause["id"], "REVIEWED", "reviewer", "matched signed agreement")
        self.assertEqual(reviewed["review_status"], "REVIEWED")
        events = self.repo.list_audit_events("ORG-1")
        self.assertTrue(any(e["entity_id"] == self.clause["id"] and e["event_type"] == "REVIEW" for e in events))

    def test_rule_cannot_be_reviewed_before_source_clause(self):
        rule = self.store.add_royalty_rule(
            "ORG-1", self.version_id, self.clause["id"], "PERCENTAGE_NET_SALES", "EUR", "analyst", rate=Decimal("0.05")
        )
        with self.assertRaises(ValueError):
            self.store.set_rule_review_status("ORG-1", rule["id"], "REVIEWED", "reviewer", "checked")

    def test_reviewed_rule_requires_reviewed_clause(self):
        self.store.set_clause_review_status("ORG-1", self.clause["id"], "REVIEWED", "reviewer", "checked")
        rule = self.store.add_royalty_rule(
            "ORG-1", self.version_id, self.clause["id"], "PERCENTAGE_NET_SALES", "EUR", "analyst", rate=Decimal("0.05")
        )
        reviewed = self.store.set_rule_review_status("ORG-1", rule["id"], "REVIEWED", "reviewer", "recalculated")
        self.assertEqual(reviewed["review_status"], "REVIEWED")

    def test_review_cannot_be_reset_to_unreviewed(self):
        with self.assertRaises(ValueError):
            self.store.set_clause_review_status("ORG-1", self.clause["id"], "UNREVIEWED", "reviewer", "reset")


if __name__ == "__main__":
    unittest.main()
