import unittest

from founder_control_center.app import create_app


class RegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()

    def test_future_company_registers_with_unknown_operational_truth(self):
        response = self.client.post("/api/companies/register", json={
            "id": "future-company",
            "name": "Future Company",
            "mission": "Validate a future company without inventing business truth.",
            "repository": "owner/future-company",
        })
        self.assertEqual(response.status_code, 201)
        company = response.get_json()["company"]
        self.assertEqual(company["status"], "UNKNOWN")
        self.assertEqual(company["data_freshness"], "UNKNOWN")
        self.assertEqual(company["revenue"]["state"], "UNKNOWN")
        self.assertEqual(company["repository"]["full_name"], "owner/future-company")

    def test_duplicate_company_id_is_rejected_without_overwrite(self):
        payload = {
            "id": "duplicate-company",
            "name": "Original Company",
            "mission": "Establish the original registry entry.",
        }
        first = self.client.post("/api/companies/register", json=payload)
        self.assertEqual(first.status_code, 201)
        duplicate = self.client.post("/api/companies/register", json={
            "id": "duplicate-company",
            "name": "Duplicate",
            "mission": "Should not overwrite existing truth.",
        })
        self.assertEqual(duplicate.status_code, 400)
        current = self.client.get("/api/companies/duplicate-company").get_json()
        self.assertEqual(current["name"], "Original Company")
        self.assertEqual(current["mission"], "Establish the original registry entry.")

    def test_repository_path_injection_is_rejected(self):
        response = self.client.post("/api/companies/register", json={
            "id": "unsafe-repo-company",
            "name": "Unsafe Repo Company",
            "mission": "Must never expand GitHub API authority.",
            "repository": "owner/repo/../../user",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_company_manifest")

    def test_null_required_identity_is_rejected_not_stringified(self):
        response = self.client.post("/api/companies/register", json={
            "id": "null-name-company",
            "name": None,
            "mission": "Missing name must stay missing.",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("must be strings", response.get_json()["detail"])

    def test_non_object_json_is_rejected_without_server_error(self):
        response = self.client.post("/api/companies/register", json=["not", "an", "object"])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_company_manifest")

    def test_oversized_identity_fields_are_rejected_not_truncated(self):
        cases = [
            ("oversized-name", {"name": "N" * 121}, "name must be at most 120 characters"),
            ("oversized-mission", {"mission": "M" * 1001}, "mission must be at most 1000 characters"),
            ("oversized-kind", {"kind": "K" * 81}, "kind must be at most 80 characters"),
        ]
        for company_id, override, expected in cases:
            payload = {
                "id": company_id,
                "name": "Bounded Company",
                "mission": "Reject silent identity truncation.",
                "kind": "company",
            }
            payload.update(override)
            response = self.client.post("/api/companies/register", json=payload)
            self.assertEqual(response.status_code, 400, company_id)
            self.assertIn(expected, response.get_json()["detail"], company_id)
            self.assertEqual(self.client.get(f"/api/companies/{company_id}").status_code, 404, company_id)


if __name__ == "__main__":
    unittest.main()
