import unittest

from repository import RoyaltyRepository
from web_app import MAX_TEXT_EVIDENCE_BYTES, create_app


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.app = create_app(api_keys={"ORG-1": "secret-one", "ORG-2": "secret-two"}, repository=self.repo)
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.repo.close()

    def payload(self):
        return {
            "organization_id": "ORG-1",
            "case_id": "CASE-1",
            "licensee_id": "LICENSEE-1",
            "agreement_id": "AGR-1",
            "annual_reported_royalty": "1500000",
            "audit_deadline": "2026-10-01",
            "audit_right_supported": True,
            "contract_version_complete": True,
            "as_of_date": "2026-08-29",
            "rule": {
                "rule_id": "RULE-1",
                "basis": "PERCENTAGE_NET_SALES",
                "rate": "0.05",
                "currency": "EUR",
                "source_clause": "Agreement §4.2"
            },
            "period_input": {
                "gross_sales": "120000",
                "permitted_deductions": "10000",
                "reported_royalty": "4500",
                "paid_royalty": "4500"
            }
        }

    def auth(self, secret="secret-one"):
        return {"X-RoyaltyRecover-API-Key": secret}

    def bootstrap_org(self, name="Alpha"):
        response = self.client.post("/api/v1/organization", json={"name": name}, headers=self.auth())
        self.assertEqual(response.status_code, 200)

    def test_health_is_non_sensitive_and_public(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["claim_generation"])

    def test_scan_requires_authentication(self):
        response = self.client.post("/api/v1/recoverability/scan", json=self.payload())
        self.assertEqual(response.status_code, 401)

    def test_missing_service_key_map_fails_closed(self):
        repo = RoyaltyRepository.memory()
        try:
            app = create_app(api_keys={}, repository=repo)
            app.testing = True
            response = app.test_client().post("/api/v1/recoverability/scan", json=self.payload())
            self.assertEqual(response.status_code, 503)
        finally:
            repo.close()

    def test_cross_tenant_key_is_rejected(self):
        response = self.client.post("/api/v1/recoverability/scan", json=self.payload(), headers=self.auth("secret-two"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "organization_scope_mismatch")

    def test_supported_variance_is_returned_but_not_claim_ready(self):
        response = self.client.post("/api/v1/recoverability/scan", json=self.payload(), headers=self.auth())
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["calculation"]["state"], "RECOVERY_CANDIDATE")
        self.assertEqual(data["calculation"]["recoverable_candidate"], "1000.00")
        self.assertFalse(data["claim_ready"])
        self.assertEqual(data["organization_id"], "ORG-1")
        self.assertIn("not a legal claim", data["disclaimer"])

    def test_missing_clause_returns_unknown_not_money(self):
        payload = self.payload()
        del payload["rule"]["source_clause"]
        response = self.client.post("/api/v1/recoverability/scan", json=payload, headers=self.auth())
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["calculation"]["state"], "UNKNOWN")
        self.assertIsNone(data["calculation"]["recoverable_candidate"])
        self.assertFalse(data["claim_ready"])

    def test_invalid_decimal_is_rejected(self):
        payload = self.payload()
        payload["period_input"]["gross_sales"] = "not-a-number"
        response = self.client.post("/api/v1/recoverability/scan", json=payload, headers=self.auth())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_input")

    def test_security_headers_are_present(self):
        response = self.client.get("/health")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_persistent_agreement_workflow_is_tenant_scoped(self):
        self.bootstrap_org()
        licensor = self.client.post("/api/v1/licensors", json={"legal_name": "Alpha University"}, headers=self.auth()).get_json()["licensor"]
        licensee = self.client.post("/api/v1/licensees", json={"legal_name": "Tech Licensee Ltd"}, headers=self.auth()).get_json()["licensee"]
        agreement_response = self.client.post(
            "/api/v1/agreements",
            json={"licensor_id": licensor["id"], "licensee_id": licensee["id"], "title": "Patent Licence", "governing_law": "Portugal"},
            headers=self.auth(),
        )
        self.assertEqual(agreement_response.status_code, 201)
        agreement = agreement_response.get_json()["agreement"]
        same_org = self.client.get(f"/api/v1/agreements/{agreement['id']}", headers=self.auth())
        other_org = self.client.get(f"/api/v1/agreements/{agreement['id']}", headers=self.auth("secret-two"))
        self.assertEqual(same_org.status_code, 200)
        self.assertEqual(other_org.status_code, 404)

    def test_version_and_evidence_hash_text_but_do_not_persist_raw_text(self):
        self.bootstrap_org()
        licensor = self.client.post("/api/v1/licensors", json={"legal_name": "Alpha University"}, headers=self.auth()).get_json()["licensor"]
        licensee = self.client.post("/api/v1/licensees", json={"legal_name": "Tech Licensee Ltd"}, headers=self.auth()).get_json()["licensee"]
        agreement = self.client.post("/api/v1/agreements", json={"licensor_id": licensor["id"], "licensee_id": licensee["id"], "title": "Patent Licence"}, headers=self.auth()).get_json()["agreement"]
        version_response = self.client.post(
            f"/api/v1/agreements/{agreement['id']}/versions",
            json={"version_label": "v1", "content_utf8": "Royalty clause text", "effective_from": "2026-01-01"},
            headers=self.auth(),
        )
        evidence_response = self.client.post(
            "/api/v1/evidence",
            json={"evidence_type": "ROYALTY_STATEMENT", "content_utf8": "Q2 statement", "metadata": {"period": "2026-Q2"}},
            headers=self.auth(),
        )
        self.assertEqual(version_response.status_code, 201)
        self.assertEqual(evidence_response.status_code, 201)
        version = version_response.get_json()["agreement_version"]
        evidence = evidence_response.get_json()["evidence"]
        self.assertFalse(version["content_persisted"])
        self.assertFalse(evidence["content_persisted"])
        self.assertEqual(len(version["document_sha256"]), 64)
        self.assertEqual(len(evidence["source_sha256"]), 64)
        self.assertNotIn("Royalty clause text", str(version))
        self.assertNotIn("Q2 statement", str(evidence))

    def test_oversized_text_ingestion_fails_closed(self):
        self.bootstrap_org()
        response = self.client.post(
            "/api/v1/evidence",
            json={"evidence_type": "ROYALTY_STATEMENT", "content_utf8": "x" * (MAX_TEXT_EVIDENCE_BYTES + 1)},
            headers=self.auth(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_input")

    def test_audit_event_endpoint_does_not_cross_org_scope(self):
        self.bootstrap_org()
        self.client.post("/api/v1/licensors", json={"legal_name": "Alpha University"}, headers=self.auth())
        events = self.client.get("/api/v1/audit-events", headers=self.auth()).get_json()["items"]
        self.assertTrue(events)
        self.assertTrue(all(item["organization_id"] == "ORG-1" for item in events))


if __name__ == "__main__":
    unittest.main()
