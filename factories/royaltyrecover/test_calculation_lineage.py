import unittest

from repository import NotFoundError, RoyaltyRepository, canonical_input_hash


class CalculationLineageTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.repo.ensure_organization("ORG-A", "Alpha", "tester")
        self.repo.ensure_organization("ORG-B", "Beta", "tester")
        licensor = self.repo.create_licensor("ORG-A", "Licensor A", "tester")
        licensee = self.repo.create_licensee("ORG-A", "Licensee A", "tester")
        self.agreement = self.repo.create_agreement("ORG-A", licensor["id"], licensee["id"], "Technology Licence", "tester")
        self.v1 = self.repo.add_agreement_version("ORG-A", self.agreement["id"], "v1", b"Agreement v1", "tester")

    def tearDown(self):
        self.repo.close()

    def create_run(self, inputs=None):
        inputs = inputs or {"sales_dataset": "sha256:abc", "statement": "sha256:def"}
        return self.repo.create_calculation_run(
            "ORG-A", self.agreement["id"], self.v1["id"],
            "2026-01-01", "2026-03-31", "0.2.0", inputs, "tester"
        )

    def test_canonical_input_hash_is_order_independent(self):
        self.assertEqual(canonical_input_hash({"b": 2, "a": 1}), canonical_input_hash({"a": 1, "b": 2}))

    def test_calculation_run_is_tenant_scoped_and_lineage_bound(self):
        inputs = {"sales_dataset": "sha256:abc", "statement": "sha256:def"}
        run = self.create_run(inputs)
        self.assertEqual(run["input_hash"], canonical_input_hash(inputs))
        self.assertEqual(run["agreement_version_id"], self.v1["id"])
        with self.assertRaises(NotFoundError):
            self.repo.get_calculation_run("ORG-B", run["id"])

    def test_input_change_marks_run_stale(self):
        run = self.create_run({"statement": "sha256:old"})
        status = self.repo.calculation_run_freshness(
            "ORG-A", run["id"], self.v1["id"], "0.2.0", {"statement": "sha256:new"}
        )
        self.assertEqual(status["status"], "STALE")
        self.assertEqual(status["reasons"], ["INPUT_DATA_CHANGED"])

    def test_agreement_and_engine_change_mark_run_stale(self):
        run = self.create_run({"data": "x"})
        v2 = self.repo.add_agreement_version("ORG-A", self.agreement["id"], "v2", b"amended", "tester")
        status = self.repo.calculation_run_freshness(
            "ORG-A", run["id"], v2["id"], "0.3.0", {"data": "x"}
        )
        self.assertEqual(status["status"], "STALE")
        self.assertEqual(status["reasons"], ["AGREEMENT_VERSION_CHANGED", "ENGINE_VERSION_CHANGED"])

    def test_current_requires_exact_version_engine_and_input(self):
        inputs = {"data": "same"}
        run = self.create_run(inputs)
        status = self.repo.calculation_run_freshness("ORG-A", run["id"], self.v1["id"], "0.2.0", inputs)
        self.assertEqual(status["status"], "CURRENT")
        self.assertEqual(status["reasons"], [])


if __name__ == "__main__":
    unittest.main()
