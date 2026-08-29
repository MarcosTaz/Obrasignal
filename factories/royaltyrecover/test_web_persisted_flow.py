import unittest

from repository import RoyaltyRepository
from web_app import create_app


class WebPersistedFlowTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        config = {"keys": [
            {"key_id": "a1", "organization_id": "ORG-1", "secret": "analyst", "role": "ANALYST"},
            {"key_id": "r1", "organization_id": "ORG-1", "secret": "reviewer", "role": "REVIEWER"},
            {"key_id": "a2", "organization_id": "ORG-2", "secret": "other", "role": "ANALYST"},
        ]}
        self.app = create_app(api_keys=config, repository=self.repo)
        self.app.testing = True
        self.client = self.app.test_client()
        self.analyst = {"X-RoyaltyRecover-API-Key": "analyst"}
        self.reviewer = {"X-RoyaltyRecover-API-Key": "reviewer"}
        self.other = {"X-RoyaltyRecover-API-Key": "other"}
        self.client.post("/api/v1/organization", json={"name": "One"}, headers=self.analyst)
        self.client.post("/api/v1/organization", json={"name": "Two"}, headers=self.other)
        licensor = self.client.post("/api/v1/licensors", json={"legal_name": "University"}, headers=self.analyst).get_json()["licensor"]
        licensee = self.client.post("/api/v1/licensees", json={"legal_name": "Licensee"}, headers=self.analyst).get_json()["licensee"]
        self.agreement = self.client.post("/api/v1/agreements", json={
            "licensor_id": licensor["id"], "licensee_id": licensee["id"], "title": "Patent Licence"
        }, headers=self.analyst).get_json()["agreement"]
        self.version = self.client.post(f"/api/v1/agreements/{self.agreement['id']}/versions", json={
            "version_label": "v1", "content_utf8": "Royalty clause: five percent of net sales."
        }, headers=self.analyst).get_json()["agreement_version"]
        contract_ev = self.client.post("/api/v1/evidence", json={
            "evidence_type": "AGREEMENT", "content_utf8": "Royalty clause: five percent of net sales."
        }, headers=self.analyst).get_json()["evidence"]
        statement_ev = self.client.post("/api/v1/evidence", json={
            "evidence_type": "ROYALTY_STATEMENT", "content_utf8": "gross=120000 deductions=10000 royalty=4500"
        }, headers=self.analyst).get_json()["evidence"]
        self.statement_evidence_id = statement_ev["id"]
        clause = self.client.post(f"/api/v1/agreement-versions/{self.version['id']}/clauses", json={
            "clause_ref": "4.2", "clause_type": "ROYALTY_RATE", "text_excerpt": "Five percent of Net Sales.",
            "evidence_id": contract_ev["id"]
        }, headers=self.analyst).get_json()["clause"]
        reviewed_clause = self.client.post(f"/api/v1/clauses/{clause['id']}/review", json={
            "review_status": "REVIEWED", "rationale": "matched source agreement"
        }, headers=self.reviewer)
        self.assertEqual(reviewed_clause.status_code, 200)
        rule = self.client.post(f"/api/v1/agreement-versions/{self.version['id']}/royalty-rules", json={
            "clause_id": clause["id"], "basis": "PERCENTAGE_NET_SALES", "currency": "EUR", "rate": "0.05"
        }, headers=self.analyst).get_json()["royalty_rule"]
        reviewed_rule = self.client.post(f"/api/v1/royalty-rules/{rule['id']}/review", json={
            "review_status": "REVIEWED", "rationale": "rate recalculated against clause"
        }, headers=self.reviewer)
        self.assertEqual(reviewed_rule.status_code, 200)
        self.rule_id = rule["id"]

    def tearDown(self):
        self.repo.close()

    def run_scan(self):
        return self.client.post("/api/v1/persisted-scans", json={
            "agreement_id": self.agreement["id"],
            "agreement_version_id": self.version["id"],
            "rule_id": self.rule_id,
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "evidence_ids": [self.statement_evidence_id],
            "period_input": {
                "gross_sales": "120000", "permitted_deductions": "10000",
                "reported_royalty": "4500", "paid_royalty": "4500"
            }
        }, headers=self.analyst)

    def test_reviewed_source_to_register_is_end_to_end_and_non_claiming(self):
        response = self.run_scan()
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["calculation_state"], "RECOVERY_CANDIDATE")
        self.assertEqual(data["recoverable_candidate"], "1000.00")
        self.assertFalse(data["claim_ready"])
        register = self.client.get("/api/v1/recoverability-register", headers=self.analyst).get_json()
        self.assertEqual(len(register["items"]), 1)
        self.assertEqual(register["items"][0]["amount_label"], "ANALYTICAL_CANDIDATE")
        self.assertFalse(register["items"][0]["claim_ready"])
        summary = self.client.get("/api/v1/recoverability-register/summary", headers=self.analyst).get_json()
        self.assertEqual(summary["analytical_candidate_total"], "1000.00")
        self.assertEqual(summary["claim_ready_count"], 0)

    def test_analyst_cannot_review_persisted_finding(self):
        finding = self.run_scan().get_json()["finding"]
        response = self.client.post(f"/api/v1/findings/{finding['id']}/review", json={
            "decision": "APPROVE_DESK_FINDING", "rationale": "checked"
        }, headers=self.analyst)
        self.assertEqual(response.status_code, 403)

    def test_reviewer_can_review_but_cannot_make_claim_ready(self):
        finding = self.run_scan().get_json()["finding"]
        response = self.client.post(f"/api/v1/findings/{finding['id']}/review", json={
            "decision": "APPROVE_DESK_FINDING", "rationale": "desk evidence supports escalation"
        }, headers=self.reviewer)
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.get_json()["review"]["claim_ready"])

    def test_other_tenant_register_is_empty(self):
        self.run_scan()
        response = self.client.get("/api/v1/recoverability-register", headers=self.other)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"], [])

    def test_persisted_scan_does_not_accept_recovery_amount_override(self):
        response = self.client.post("/api/v1/persisted-scans", json={
            "agreement_id": self.agreement["id"], "agreement_version_id": self.version["id"], "rule_id": self.rule_id,
            "period_start": "2026-01-01", "period_end": "2026-03-31", "evidence_ids": [self.statement_evidence_id],
            "recoverable_candidate": "999999999", "period_input": {
                "gross_sales": "120000", "permitted_deductions": "10000", "reported_royalty": "4500", "paid_royalty": "4500"
            }
        }, headers=self.analyst)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["recoverable_candidate"], "1000.00")


if __name__ == "__main__":
    unittest.main()
