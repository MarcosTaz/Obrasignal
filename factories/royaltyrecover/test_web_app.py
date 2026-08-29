import unittest

from repository import RoyaltyRepository
from web_app import MAX_TEXT_EVIDENCE_BYTES, create_app


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        credentials = {
            "keys": [
                {"key_id": "analyst-1", "organization_id": "ORG-1", "secret": "secret-one", "role": "ANALYST"},
                {"key_id": "reviewer-1", "organization_id": "ORG-1", "secret": "reviewer-one", "role": "REVIEWER"},
                {"key_id": "analyst-2", "organization_id": "ORG-2", "secret": "secret-two", "role": "ANALYST"},
            ]
        }
        self.app = create_app(api_keys=credentials, repository=self.repo)
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.repo.close()

    def auth(self, secret="secret-one"):
        return {"X-RoyaltyRecover-API-Key": secret}

    def bootstrap_org(self, name="Alpha"):
        response = self.client.post("/api/v1/organization", json={"name": name}, headers=self.auth())
        self.assertEqual(response.status_code, 200)

    def bootstrap_reviewed_case(self):
        self.bootstrap_org()
        licensor = self.client.post("/api/v1/licensors", json={"legal_name": "Alpha University"}, headers=self.auth()).get_json()["licensor"]
        licensee = self.client.post("/api/v1/licensees", json={"legal_name": "Tech Licensee Ltd"}, headers=self.auth()).get_json()["licensee"]
        agreement = self.client.post(
            "/api/v1/agreements",
            json={"licensor_id": licensor["id"], "licensee_id": licensee["id"], "title": "Patent Licence", "governing_law": "Portugal"},
            headers=self.auth(),
        ).get_json()["agreement"]
        version = self.client.post(
            f"/api/v1/agreements/{agreement['id']}/versions",
            json={"version_label": "v1", "content_utf8": "Section 4.2: five percent of net sales", "effective_from": "2026-01-01"},
            headers=self.auth(),
        ).get_json()["agreement_version"]
        evidence = self.client.post(
            "/api/v1/evidence",
            json={"evidence_type": "ROYALTY_STATEMENT", "content_utf8": "gross=120000 deductions=10000 paid=4500", "metadata": {"period": "2026-Q2"}},
            headers=self.auth(),
        ).get_json()["evidence"]
        clause_response = self.client.post(
            f"/api/v1/agreement-versions/{version['id']}/reviewed-clauses",
            json={"clause_ref": "Agreement §4.2", "clause_type": "ROYALTY", "text_excerpt": "five percent of net sales"},
            headers=self.auth("reviewer-one"),
        )
        self.assertEqual(clause_response.status_code, 201)
        clause = clause_response.get_json()["clause"]
        rule_response = self.client.post(
            f"/api/v1/agreement-versions/{version['id']}/reviewed-royalty-rules",
            json={"clause_id": clause["id"], "basis": "PERCENTAGE_NET_SALES", "rate": "0.05", "currency": "EUR"},
            headers=self.auth("reviewer-one"),
        )
        self.assertEqual(rule_response.status_code, 201)
        rule = rule_response.get_json()["royalty_rule"]
        return agreement, version, evidence, clause, rule

    def persisted_payload(self, agreement, version, evidence, rule):
        return {
            "organization_id": "ORG-1",
            "agreement_id": agreement["id"],
            "agreement_version_id": version["id"],
            "rule_id": rule["id"],
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "evidence_ids": [evidence["id"]],
            "period_input": {
                "gross_sales": "120000",
                "permitted_deductions": "10000",
                "reported_royalty": "4500",
                "paid_royalty": "4500",
            },
        }

    def test_health_is_non_sensitive_and_public(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["claim_generation"])

    def test_scan_requires_authentication(self):
        response = self.client.post("/api/v1/recoverability/persisted-scan", json={})
        self.assertEqual(response.status_code, 401)

    def test_missing_service_key_map_fails_closed(self):
        repo = RoyaltyRepository.memory()
        try:
            app = create_app(api_keys={}, repository=repo)
            app.testing = True
            response = app.test_client().post("/api/v1/recoverability/persisted-scan", json={})
            self.assertEqual(response.status_code, 503)
        finally:
            repo.close()

    def test_legacy_direct_rule_scan_is_rejected_even_when_authenticated(self):
        response = self.client.post(
            "/api/v1/recoverability/scan",
            json={"organization_id": "ORG-1", "rule": {"rate": "0.99"}},
            headers=self.auth(),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "persisted_lineage_required")

    def test_cross_tenant_key_is_rejected_before_scan(self):
        response = self.client.post(
            "/api/v1/recoverability/persisted-scan",
            json={"organization_id": "ORG-1"},
            headers=self.auth("secret-two"),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "organization_scope_mismatch")

    def test_analyst_cannot_mark_contract_source_as_human_reviewed(self):
        self.bootstrap_org()
        licensor = self.client.post("/api/v1/licensors", json={"legal_name": "Alpha"}, headers=self.auth()).get_json()["licensor"]
        licensee = self.client.post("/api/v1/licensees", json={"legal_name": "Beta"}, headers=self.auth()).get_json()["licensee"]
        agreement = self.client.post("/api/v1/agreements", json={"licensor_id": licensor["id"], "licensee_id": licensee["id"], "title": "Licence"}, headers=self.auth()).get_json()["agreement"]
        version = self.client.post(f"/api/v1/agreements/{agreement['id']}/versions", json={"version_label": "v1", "content_utf8": "clause"}, headers=self.auth()).get_json()["agreement_version"]
        response = self.client.post(
            f"/api/v1/agreement-versions/{version['id']}/reviewed-clauses",
            json={"clause_ref": "4.2", "clause_type": "ROYALTY"},
            headers=self.auth(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "insufficient_role")

    def test_reviewed_persisted_variance_is_returned_but_not_claim_ready(self):
        agreement, version, evidence, _, rule = self.bootstrap_reviewed_case()
        response = self.client.post(
            "/api/v1/recoverability/persisted-scan",
            json=self.persisted_payload(agreement, version, evidence, rule),
            headers=self.auth(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["calculation"]["state"], "RECOVERY_CANDIDATE")
        self.assertEqual(data["calculation"]["recoverable_candidate"], "1000.00")
        self.assertFalse(data["claim_ready"])
        self.assertEqual(data["organization_id"], "ORG-1")
        self.assertIn("not a legal claim", data["disclaimer"])
        self.assertEqual(data["finding"]["source_clause_id"], self.repo.conn.execute("SELECT id FROM clauses").fetchone()["id"])

    def test_scan_rejects_missing_tenant_scoped_evidence(self):
        agreement, version, evidence, _, rule = self.bootstrap_reviewed_case()
        payload = self.persisted_payload(agreement, version, evidence, rule)
        payload["evidence_ids"] = []
        response = self.client.post("/api/v1/recoverability/persisted-scan", json=payload, headers=self.auth())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_input")

    def test_invalid_decimal_is_rejected(self):
        agreement, version, evidence, _, rule = self.bootstrap_reviewed_case()
        payload = self.persisted_payload(agreement, version, evidence, rule)
        payload["period_input"]["gross_sales"] = "not-a-number"
        response = self.client.post("/api/v1/recoverability/persisted-scan", json=payload, headers=self.auth())
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
