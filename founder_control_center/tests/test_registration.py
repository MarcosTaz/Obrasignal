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


if __name__ == "__main__":
    unittest.main()
