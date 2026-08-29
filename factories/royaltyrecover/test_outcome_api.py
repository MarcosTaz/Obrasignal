import unittest
from decimal import Decimal

from application import create_full_app
from finding_store import FindingStore
from repository import RoyaltyRepository
from royalty_engine import FindingState


class OutcomeApiTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        keys = {"keys": [
            {"key_id": "a", "organization_id": "ORG-A", "secret": "analyst", "role": "ANALYST"},
            {"key_id": "r", "organization_id": "ORG-A", "secret": "reviewer", "role": "REVIEWER"},
        ]}
        app = create_full_app(api_keys=keys, repository=self.repo)
        app.testing = True
        self.client = app.test_client()
        self.a = {"X-RoyaltyRecover-API-Key": "analyst"}
        self.r = {"X-RoyaltyRecover-API-Key": "reviewer"}
        self.repo.ensure_organization("ORG-A", "Alpha", "system")
        licensor = self.repo.create_licensor("ORG-A", "University", "system")
        licensee = self.repo.create_licensee("ORG-A", "Licensee", "system")
        self.agreement = self.repo.create_agreement("ORG-A", licensor["id"], licensee["id"], "Patent Licence", "system")
        findings = FindingStore(self.repo)
        self.finding = findings.create_finding(
            "ORG-A", self.agreement["id"], "PERSISTED_RULE_SCAN", FindingState.RECOVERY_CANDIDATE,
            "SUPPORTED_DETERMINISTIC_ARITHMETIC", "analyst", amount=Decimal("1000"), currency="EUR"
        )
        findings.add_review("ORG-A", self.finding["id"], "reviewer", "REVIEWER", "ROUTE_TO_FORMAL_AUDIT", "audit required")
        self.outcome_ev = self.repo.add_evidence("ORG-A", "AUDIT_OUTCOME", b"confirmed adjustment", "reviewer")
        self.payment_ev = self.repo.add_evidence("ORG-A", "PAYMENT", b"bank receipt", "analyst")

    def tearDown(self):
        self.repo.close()

    def test_analyst_cannot_create_recovery_outcome(self):
        response = self.client.post(f"/api/v1/findings/{self.finding['id']}/outcomes", json={
            "outcome_type": "SETTLED", "evidence_id": self.outcome_ev["id"]
        }, headers=self.a)
        self.assertEqual(response.status_code, 403)

    def test_end_to_end_payment_recovery_stays_unverified_until_reviewer_verifies(self):
        outcome = self.client.post(f"/api/v1/findings/{self.finding['id']}/outcomes", json={
            "outcome_type": "SETTLED", "evidence_id": self.outcome_ev["id"]
        }, headers=self.r)
        self.assertEqual(outcome.status_code, 201)
        outcome_id = outcome.get_json()["outcome"]["id"]
        payment = self.client.post("/api/v1/payments", json={
            "agreement_id": self.agreement["id"], "payment_date": "2026-08-29", "currency": "EUR",
            "amount": "1000", "evidence_id": self.payment_ev["id"], "payment_reference": "BANK-1"
        }, headers=self.a)
        self.assertEqual(payment.status_code, 201)
        payment_id = payment.get_json()["payment"]["id"]
        denied = self.client.post(f"/api/v1/outcomes/{outcome_id}/recovered-amounts", json={
            "payment_id": payment_id, "amount": "1000", "currency": "EUR", "evidence_id": self.payment_ev["id"]
        }, headers=self.a)
        self.assertEqual(denied.status_code, 403)
        recovered = self.client.post(f"/api/v1/outcomes/{outcome_id}/recovered-amounts", json={
            "payment_id": payment_id, "amount": "1000", "currency": "EUR", "evidence_id": self.payment_ev["id"]
        }, headers=self.r)
        self.assertEqual(recovered.status_code, 201)
        recovered_id = recovered.get_json()["recovered_amount"]["id"]
        self.assertFalse(recovered.get_json()["verified"])
        verify_denied = self.client.post(f"/api/v1/recovered-amounts/{recovered_id}/verify", json={"rationale": "matched"}, headers=self.a)
        self.assertEqual(verify_denied.status_code, 403)
        verified = self.client.post(f"/api/v1/recovered-amounts/{recovered_id}/verify", json={"rationale": "bank payment matched settlement evidence"}, headers=self.r)
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.get_json()["verified"])
        summary = self.client.get("/api/v1/recoveries/verified-summary", headers=self.a).get_json()
        self.assertEqual(summary["verified_recovery_count"], 1)
        self.assertEqual(summary["verified_recovery_total"], "1000")


if __name__ == "__main__":
    unittest.main()
