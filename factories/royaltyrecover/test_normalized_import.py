import unittest
from decimal import Decimal

from normalized_import import NormalizedSalesRow, import_sales_batch, list_sales_records
from repository import ConflictError, NotFoundError, RoyaltyRepository


class NormalizedImportTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.repo.ensure_organization("ORG-A", "Alpha", "system")
        self.repo.ensure_organization("ORG-B", "Beta", "system")
        licensor_a = self.repo.create_licensor("ORG-A", "University A", "system")
        licensee_a = self.repo.create_licensee("ORG-A", "Licensee A", "system")
        self.agreement_a = self.repo.create_agreement("ORG-A", licensor_a["id"], licensee_a["id"], "Licence A", "system")
        licensor_b = self.repo.create_licensor("ORG-B", "University B", "system")
        licensee_b = self.repo.create_licensee("ORG-B", "Licensee B", "system")
        self.agreement_b = self.repo.create_agreement("ORG-B", licensor_b["id"], licensee_b["id"], "Licence B", "system")
        self.evidence_a = self.repo.add_evidence("ORG-A", "SOURCE_EXPORT", b"source export a", "analyst")
        self.evidence_b = self.repo.add_evidence("ORG-B", "SOURCE_EXPORT", b"source export b", "analyst")

    def tearDown(self):
        self.repo.close()

    def rows(self):
        return [
            NormalizedSalesRow("row-1", "2026-01-10", gross_amount=Decimal("100.25"), currency="eur"),
            NormalizedSalesRow("row-2", "2026-01-11", units=Decimal("3")),
        ]

    def test_import_preserves_dataset_and_row_provenance(self):
        result = import_sales_batch(
            self.repo, "ORG-A", self.agreement_a["id"], "WELLSPRING_EXPORT", "dataset-2026-q1",
            self.rows(), self.evidence_a["id"], "analyst",
        )
        self.assertEqual(result.row_count, 2)
        self.assertEqual(len(result.dataset_sha256), 64)
        stored = list_sales_records(self.repo, "ORG-A", self.agreement_a["id"], "dataset-2026-q1")
        self.assertEqual([row["source_row_key"] for row in stored], ["row-1", "row-2"])
        self.assertTrue(all(len(row["row_sha256"]) == 64 for row in stored))
        events = self.repo.list_audit_events("ORG-A")
        self.assertTrue(any(event["event_type"] == "IMPORT" and event["entity_id"] == "dataset-2026-q1" for event in events))

    def test_same_source_row_cannot_be_silently_reimported(self):
        import_sales_batch(self.repo, "ORG-A", self.agreement_a["id"], "CSV", "dataset-1", self.rows(), self.evidence_a["id"], "analyst")
        with self.assertRaises(ConflictError):
            import_sales_batch(self.repo, "ORG-A", self.agreement_a["id"], "CSV", "dataset-1", self.rows(), self.evidence_a["id"], "analyst")
        self.assertEqual(len(list_sales_records(self.repo, "ORG-A", self.agreement_a["id"])), 2)

    def test_cross_tenant_evidence_is_rejected(self):
        with self.assertRaises(NotFoundError):
            import_sales_batch(
                self.repo, "ORG-A", self.agreement_a["id"], "CSV", "dataset-1", self.rows(), self.evidence_b["id"], "analyst"
            )

    def test_cross_tenant_agreement_read_is_rejected(self):
        with self.assertRaises(NotFoundError):
            list_sales_records(self.repo, "ORG-B", self.agreement_a["id"])

    def test_duplicate_row_key_inside_batch_fails_before_write(self):
        rows = [
            NormalizedSalesRow("dup", "2026-01-01", gross_amount=Decimal("10"), currency="EUR"),
            NormalizedSalesRow("dup", "2026-01-02", gross_amount=Decimal("20"), currency="EUR"),
        ]
        with self.assertRaises(ValueError):
            import_sales_batch(self.repo, "ORG-A", self.agreement_a["id"], "CSV", "dataset-dup", rows, self.evidence_a["id"], "analyst")
        self.assertEqual(list_sales_records(self.repo, "ORG-A", self.agreement_a["id"]), [])

    def test_gross_amount_requires_currency(self):
        with self.assertRaises(ValueError):
            import_sales_batch(
                self.repo, "ORG-A", self.agreement_a["id"], "CSV", "dataset-bad",
                [NormalizedSalesRow("r", "2026-01-01", gross_amount=Decimal("10"))], self.evidence_a["id"], "analyst",
            )


if __name__ == "__main__":
    unittest.main()
