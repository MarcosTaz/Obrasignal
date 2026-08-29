import unittest

from web_app import create_app


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(api_key="test-secret")
        self.app.testing = True
        self.client = self.app.test_client()

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

    def auth(self):
        return {"X-RoyaltyRecover-API-Key": "test-secret"}

    def test_health_is_non_sensitive_and_public(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["claim_generation"])

    def test_scan_requires_authentication(self):
        response = self.client.post("/api/v1/recoverability/scan", json=self.payload())
        self.assertEqual(response.status_code, 401)

    def test_missing_service_key_fails_closed(self):
        app = create_app(api_key="")
        app.testing = True
        response = app.test_client().post("/api/v1/recoverability/scan", json=self.payload())
        self.assertEqual(response.status_code, 503)

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


if __name__ == "__main__":
    unittest.main()
