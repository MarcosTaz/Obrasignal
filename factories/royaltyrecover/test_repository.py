import unittest

from repository import NotFoundError, RoyaltyRepository, sha256_bytes


class RepositoryIsolationTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.repo.ensure_organization("ORG-A", "Alpha", "tester")
        self.repo.ensure_organization("ORG-B", "Beta", "tester")

    def tearDown(self):
        self.repo.close()

    def create_agreement(self, org_id="ORG-A"):
        licensor = self.repo.create_licensor(org_id, f"{org_id} Licensor", "tester")
        licensee = self.repo.create_licensee(org_id, f"{org_id} Licensee", "tester")
        return self.repo.create_agreement(org_id, licensor["id"], licensee["id"], "Technology Licence", "tester")

    def test_cross_tenant_licensor_read_is_not_found(self):
        licensor = self.repo.create_licensor("ORG-A", "Licensor A", "tester")
        with self.assertRaises(NotFoundError):
            self.repo.get_licensor("ORG-B", licensor["id"])

    def test_cross_tenant_agreement_composition_is_rejected(self):
        licensor = self.repo.create_licensor("ORG-A", "Licensor A", "tester")
        licensee = self.repo.create_licensee("ORG-B", "Licensee B", "tester")
        with self.assertRaises(NotFoundError):
            self.repo.create_agreement("ORG-A", licensor["id"], licensee["id"], "Bad mix", "tester")

    def test_agreement_version_is_immutable_lineage_record(self):
        agreement = self.create_agreement()
        content = b"Agreement version 1"
        version = self.repo.add_agreement_version("ORG-A", agreement["id"], "v1", content, "tester", effective_from="2026-01-01")
        self.assertEqual(version["document_sha256"], sha256_bytes(content))
        with self.assertRaises(NotFoundError):
            self.repo.get_agreement_version("ORG-B", version["id"])

    def test_duplicate_version_label_is_rejected_by_schema(self):
        agreement = self.create_agreement()
        self.repo.add_agreement_version("ORG-A", agreement["id"], "v1", b"one", "tester")
        with self.assertRaises(Exception):
            self.repo.add_agreement_version("ORG-A", agreement["id"], "v1", b"two", "tester")

    def test_evidence_hash_and_scope(self):
        content = b"statement row evidence"
        evidence = self.repo.add_evidence("ORG-A", "ROYALTY_STATEMENT", content, "tester", metadata={"period": "2026-Q2"})
        self.assertEqual(evidence["source_sha256"], sha256_bytes(content))
        self.assertEqual(evidence["metadata"]["period"], "2026-Q2")
        with self.assertRaises(NotFoundError):
            self.repo.get_evidence("ORG-B", evidence["id"])

    def test_audit_events_are_tenant_scoped(self):
        self.repo.create_licensor("ORG-A", "Licensor A", "tester")
        self.repo.create_licensor("ORG-B", "Licensor B", "tester")
        events_a = self.repo.list_audit_events("ORG-A")
        events_b = self.repo.list_audit_events("ORG-B")
        self.assertTrue(events_a)
        self.assertTrue(events_b)
        self.assertTrue(all(event["organization_id"] == "ORG-A" for event in events_a))
        self.assertTrue(all(event["organization_id"] == "ORG-B" for event in events_b))


if __name__ == "__main__":
    unittest.main()
