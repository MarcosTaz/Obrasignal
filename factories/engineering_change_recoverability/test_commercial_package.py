import json
import unittest
from pathlib import Path

from commercial_package import build_commercial_package
from engine import analyze_case

ROOT = Path(__file__).resolve().parent


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((ROOT / "synthetic_cases.json").read_text())

    def test_recoverable_package_is_traceable(self):
        case = next(x for x in self.cases if x["change_id"] == "EC-ALPHA-001")
        analysis = analyze_case(case)
        package = build_commercial_package(case, analysis)
        self.assertEqual(package["economic_outcome"]["recoverable_amount"], 140000.0)
        self.assertEqual(package["notice"]["state"], "ON_TIME")
        self.assertTrue(package["evidence_graph"]["edges"])
        self.assertEqual(package["missing_evidence"], [])
        self.assertEqual(len(package["audit_trail"][0]["input_sha256"]), 64)

    def test_zero_recovery_is_preserved_as_successful_truth(self):
        case = next(x for x in self.cases if x["change_id"] == "EC-ALPHA-002")
        package = build_commercial_package(case)
        self.assertEqual(package["economic_outcome"]["status"], "ZERO_RECOVERY")
        self.assertEqual(package["economic_outcome"]["recoverable_amount"], 0.0)
        self.assertEqual(package["mitigation"]["verified_amount"], 25000.0)

    def test_wrong_revision_does_not_generate_recoverable_package(self):
        case = next(x for x in self.cases if x["change_id"] == "EC-RT-901")
        package = build_commercial_package(case)
        self.assertEqual(package["economic_outcome"]["recoverable_amount"], 0.0)
        self.assertEqual(package["economic_outcome"]["status"], "UNKNOWN")
        self.assertTrue(package["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
