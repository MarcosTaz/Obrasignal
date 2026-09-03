import unittest
from decimal import Decimal

from finding_store import FindingStore
from repository import NotFoundError, RoyaltyRepository
from royalty_engine import FindingState


class FindingStoreTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.repo.ensure_organization("ORG-A", "Alpha", "tester")
        self.repo.ensure_organization("ORG-B", "Beta", "tester")
        self.store = FindingStore(self.repo)
        self.agreements = {}
        for org_id in ("ORG-A", "ORG-B"):
            licensor = self.repo.create_licensor(org_id, f"{org_id} Licensor", "tester")
            licensee = self.repo.create_licensee(org_id, f"{org_id} Licensee", "tester")
            self.agreements[org_id] = self.repo.create_agreement(org_id, licensor["id"], licensee["id"], "Technology Licence", "tester")

    def tearDown(self):
        self.repo.close()

    def candidate(self, org_id="ORG-A", amount=Decimal("1000"), currency="EUR"):
        return self.store.create_finding(
            org_id,
            self.agreements[org_id]["id"],
            "EXPECTED_VS_PAID",
            FindingState.RECOVERY_CANDIDATE,
            "SUPPORTED_ARITHMETIC",
            "tester",
            amount=amount,
            currency=currency,
        )

    def test_finding_is_tenant_scoped(self):
        finding = self.candidate("ORG-A")
        with self.assertRaises(NotFoundError):
            self.store.get_finding("ORG-B", finding["id"])

    def test_positive_amount_is_only_allowed_for_candidate(self):
        with self.assertRaises(ValueError):
            self.store.create_finding(
                "ORG-A", self.agreements["ORG-A"]["id"], "EXPECTED_VS_PAID",
                FindingState.NEEDS_DATA, "INCOMPLETE", "tester",
                amount=Decimal("1000"), currency="EUR",
            )

    def test_review_never_sets_claim_ready(self):
        finding = self.candidate()
        review = self.store.add_review(
            "ORG-A", finding["id"], "reviewer-1", "Royalty Analyst",
            "APPROVE_DESK_FINDING", "Reviewed source lineage and arithmetic."
        )
        self.assertFalse(review["claim_ready"])
        updated = self.store.get_finding("ORG-A", finding["id"])
        self.assertEqual(updated["review_status"], "DESK_APPROVED")

    def test_non_candidate_cannot_be_approved(self):
        finding = self.store.create_finding(
            "ORG-A", self.agreements["ORG-A"]["id"], "EXPECTED_VS_PAID",
            FindingState.NO_DEFENSIBLE_RECOVERY, "SUPPORTED_ARITHMETIC", "tester",
            amount=Decimal("0"), currency="EUR",
        )
        with self.assertRaises(ValueError):
            self.store.add_review(
                "ORG-A", finding["id"], "reviewer-1", "Royalty Analyst",
                "APPROVE_DESK_FINDING", "No positive supported difference."
            )

    def test_register_includes_no_recovery_and_candidate(self):
        self.candidate()
        self.store.create_finding(
            "ORG-A", self.agreements["ORG-A"]["id"], "EXPECTED_VS_PAID",
            FindingState.NO_DEFENSIBLE_RECOVERY, "SUPPORTED_ARITHMETIC", "tester",
            amount=Decimal("0"), currency="EUR",
        )
        items = self.store.recoverability_register("ORG-A")
        self.assertEqual(len(items), 2)
        self.assertEqual({item["state"] for item in items}, {"RECOVERY_CANDIDATE", "NO_DEFENSIBLE_RECOVERY"})
        self.assertTrue(all(item["claim_ready"] is False for item in items))

    def test_summary_labels_total_as_analytical_candidate_not_recovery(self):
        self.candidate(amount=Decimal("1000"))
        self.candidate(amount=Decimal("2500"))
        summary = self.store.register_summary("ORG-A")
        self.assertEqual(summary["analytical_candidate_total"], "3500")
        self.assertEqual(summary["analytical_candidate_currency"], "EUR")
        self.assertEqual(summary["claim_ready_count"], 0)

    def test_mixed_currency_total_is_suppressed(self):
        self.candidate(amount=Decimal("1000"), currency="EUR")
        self.candidate(amount=Decimal("1000"), currency="USD")
        summary = self.store.register_summary("ORG-A")
        self.assertIsNone(summary["analytical_candidate_total"])
        self.assertTrue(summary["mixed_currency_total_suppressed"])

    def test_register_never_crosses_tenants(self):
        self.candidate("ORG-A")
        self.candidate("ORG-B")
        items_a = self.store.recoverability_register("ORG-A")
        items_b = self.store.recoverability_register("ORG-B")
        self.assertEqual(len(items_a), 1)
        self.assertEqual(len(items_b), 1)
        self.assertNotEqual(items_a[0]["finding_id"], items_b[0]["finding_id"])


if __name__ == "__main__":
    unittest.main()
