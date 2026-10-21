import copy, unittest
from commercial_package import build_commercial_package, recovery_identity
from engine import analyze_case
from synthetic_cases import CASES
class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.cases=CASES
    def test_recoverable_package_is_traceable(self):
        c=next(x for x in self.cases if x["change_id"]=="EC-ALPHA-001"); p=build_commercial_package(c,analyze_case(c))
        self.assertEqual(p["economic_outcome"]["recoverable_amount"],140000.0); self.assertEqual(p["notice"]["state"],"ON_TIME")
        self.assertTrue(p["evidence_graph"]["edges"]); self.assertEqual(p["missing_evidence"],[]); self.assertEqual(len(p["audit_trail"][0]["input_sha256"]),64)
    def test_zero_recovery_is_preserved_as_successful_truth(self):
        c=next(x for x in self.cases if x["change_id"]=="EC-ALPHA-002"); p=build_commercial_package(c)
        self.assertEqual(p["economic_outcome"]["status"],"ZERO_RECOVERY"); self.assertEqual(p["mitigation"]["verified_amount"],25000.0)
    def test_wrong_revision_does_not_generate_recoverable_package(self):
        c=next(x for x in self.cases if x["change_id"]=="EC-RT-901"); p=build_commercial_package(c)
        self.assertEqual(p["economic_outcome"]["recoverable_amount"],0.0); self.assertEqual(p["economic_outcome"]["status"],"UNKNOWN")
    def test_change_record_key_is_stable_across_versions(self):
        c=next(x for x in self.cases if x["change_id"]=="EC-ALPHA-001"); d=copy.deepcopy(c); d["change_description"]="later note"
        self.assertEqual(recovery_identity(c)["change_record_key"],recovery_identity(d)["change_record_key"])
    def test_technical_delta_key_surfaces_same_delta_under_different_change_id(self):
        c=next(x for x in self.cases if x["change_id"]=="EC-ALPHA-001"); d=copy.deepcopy(c); d["change_id"]="EC-OTHER"
        a=recovery_identity(c); b=recovery_identity(d)
        self.assertNotEqual(a["change_record_key"],b["change_record_key"]); self.assertEqual(a["technical_delta_key"],b["technical_delta_key"])
if __name__=="__main__": unittest.main()
