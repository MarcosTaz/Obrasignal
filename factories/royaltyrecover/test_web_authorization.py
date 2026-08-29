import unittest

from repository import RoyaltyRepository
from web_app import create_app


class WebAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        config = {"keys": [
            {"key_id": "analyst-1", "organization_id": "ORG-1", "secret": "analyst-secret", "role": "ANALYST"},
            {"key_id": "reviewer-1", "organization_id": "ORG-1", "secret": "review-secret", "role": "REVIEWER"},
            {"key_id": "reviewer-2", "organization_id": "ORG-2", "secret": "other-review", "role": "REVIEWER"},
        ]}
        self.app = create_app(api_keys=config, repository=self.repo)
        self.app.testing = True
        self.client = self.app.test_client()
        self.analyst = {"X-RoyaltyRecover-API-Key": "analyst-secret"}
        self.reviewer = {"X-RoyaltyRecover-API-Key": "review-secret"}
        self.other = {"X-RoyaltyRecover-API-Key": "other-review"}
        self.client.post("/api/v1/organization", json={"name": "One"}, headers=self.analyst)
        licensor = self.client.post("/api/v1/licensors", json={"legal_name": "Licensor"}, headers=self.analyst).get_json()["licensor"]
        licensee = self.client.post("/api/v1/licensees", json={"legal_name": "Licensee"}, headers=self.analyst).get_json()["licensee"]
        agreement = self.client.post("/api/v1/agreements", json={
            "licensor_id": licensor["id"], "licensee_id": licensee["id"], "title": "Licence"
        }, headers=self.analyst).get_json()["agreement"]
        version = self.client.post(f"/api/v1/agreements/{agreement['id']}/versions", json={
            "version_label": "v1", "content_utf8": "Agreement text"
        }, headers=self.analyst).get_json()["agreement_version"]
        evidence = self.client.post("/api/v1/evidence", json={
            "evidence_type": "AGREEMENT", "content_utf8": "5% of net sales"
        }, headers=self.analyst).get_json()["evidence"]
        self.version_id = version["id"]
        self.evidence_id = evidence["id"]

    def tearDown(self):
        self.repo.close()

    def create_clause(self):
        response = self.client.post(f"/api/v1/agreement-versions/{self.version_id}/clauses", json={
            "clause_ref": "4.2", "clause_type": "ROYALTY", "text_excerpt": "5% of net sales",
            "evidence_id": self.evidence_id, "review_status": "REVIEWED"
        }, headers=self.analyst)
        self.assertEqual(response.status_code, 201)
        return response.get_json()["clause"]

    def test_analyst_cannot_self_approve_clause(self):
        clause = self.create_clause()
        self.assertEqual(clause["review_status"], "UNREVIEWED")
        response = self.client.post(f"/api/v1/clauses/{clause['id']}/review", json={
            "review_status": "REVIEWED", "rationale": "checked"
        }, headers=self.analyst)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "insufficient_role")

    def test_reviewer_can_approve_clause_then_rule(self):
        clause = self.create_clause()
        response = self.client.post(f"/api/v1/clauses/{clause['id']}/review", json={
            "review_status": "REVIEWED", "rationale": "matched signed contract"
        }, headers=self.reviewer)
        self.assertEqual(response.status_code, 200)
        rule = self.client.post(f"/api/v1/agreement-versions/{self.version_id}/royalty-rules", json={
            "clause_id": clause["id"], "basis": "PERCENTAGE_NET_SALES", "currency": "EUR", "rate": "0.05",
            "review_status": "REVIEWED"
        }, headers=self.analyst).get_json()["royalty_rule"]
        self.assertEqual(rule["review_status"], "UNREVIEWED")
        response = self.client.post(f"/api/v1/royalty-rules/{rule['id']}/review", json={
            "review_status": "REVIEWED", "rationale": "recalculated against clause"
        }, headers=self.reviewer)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["royalty_rule"]["review_status"], "REVIEWED")

    def test_other_tenant_reviewer_cannot_review(self):
        self.client.post("/api/v1/organization", json={"name": "Two"}, headers=self.other)
        clause = self.create_clause()
        response = self.client.post(f"/api/v1/clauses/{clause['id']}/review", json={
            "review_status": "REVIEWED", "rationale": "wrong tenant"
        }, headers=self.other)
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
