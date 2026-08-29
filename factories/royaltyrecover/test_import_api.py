import unittest

from application import create_full_app
from repository import RoyaltyRepository


class ImportApiTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        keys = {"ORG-A": "a-secret", "ORG-B": "b-secret"}
        app = create_full_app(api_keys=keys, repository=self.repo)
        app.testing = True
        self.client = app.test_client()
        self.a = {"X-RoyaltyRecover-API-Key": "a-secret"}
        self.b = {"X-RoyaltyRecover-API-Key": "b-secret"}
        self.repo.ensure_organization("ORG-A", "Alpha", "system")
        self.repo.ensure_organization("ORG-B", "Beta", "system")
        licensor = self.repo.create_licensor("ORG-A", "University A", "system")
        licensee = self.repo.create_licensee("ORG-A", "Licensee A", "system")
        self.agreement = self.repo.create_agreement("ORG-A", licensor["id"], licensee["id"], "Licence A", "system")
        self.evidence = self.repo.add_evidence("ORG-A", "SOURCE_EXPORT", b"csv-export", "analyst")

    def tearDown(self):
        self.repo.close()

    def payload(self):
        return {
            "source_system": "WELLSPRING_EXPORT",
            "source_dataset_id": "dataset-q1",
            "evidence_id": self.evidence["id"],
            "rows": [
                {"source_row_key": "1", "transaction_date": "2026-01-01", "gross_amount": "100.00", "currency": "EUR"},
                {"source_row_key": "2", "transaction_date": "2026-01-02", "units": "3"},
            ],
        }

    def test_import_and_read_preserve_provenance(self):
        response = self.client.post(f"/api/v1/agreements/{self.agreement['id']}/sales-imports", json=self.payload(), headers=self.a)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["source_system"], "WELLSPRING_EXPORT")
        self.assertEqual(data["row_count"], 2)
        self.assertFalse(data["raw_source_content_persisted"])
        records = self.client.get(f"/api/v1/agreements/{self.agreement['id']}/sales-records?source_dataset_id=dataset-q1", headers=self.a)
        self.assertEqual(records.status_code, 200)
        self.assertEqual(len(records.get_json()["items"]), 2)

    def test_other_tenant_cannot_import_or_read_agreement(self):
        self.assertEqual(
            self.client.post(f"/api/v1/agreements/{self.agreement['id']}/sales-imports", json=self.payload(), headers=self.b).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/agreements/{self.agreement['id']}/sales-records", headers=self.b).status_code,
            404,
        )

    def test_duplicate_dataset_rows_return_conflict(self):
        first = self.client.post(f"/api/v1/agreements/{self.agreement['id']}/sales-imports", json=self.payload(), headers=self.a)
        self.assertEqual(first.status_code, 201)
        second = self.client.post(f"/api/v1/agreements/{self.agreement['id']}/sales-imports", json=self.payload(), headers=self.a)
        self.assertEqual(second.status_code, 409)


if __name__ == "__main__":
    unittest.main()
