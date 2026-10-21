import copy, unittest
from engine import analyze_case
from synthetic_cases import CASES
MANDATORY={
"NO_COST_CHANGE","SMALL_CHANGE","HIGH_COST_CHANGE","DRAWING_REVISION","MATERIAL_CHANGE","TOLERANCE_CHANGE","TEST_CHANGE",
"TOOLING_MODIFICATION","NEW_TOOLING","WIP_SCRAP","FG_OBSOLESCENCE","RAW_MATERIAL_OBSOLESCENCE","REWORK",
"SUPPLIER_CANCELLATION_FEE","MOQ_EXPOSURE","SPECIAL_FREIGHT","ENGINEERING_HOURS","QUALITY_HOURS","PPAP","VALIDATION",
"CAPACITY_LOSS","PARTIAL_MITIGATION","FULL_MITIGATION","NO_CONTRACTUAL_RIGHT","STRONG_CONTRACTUAL_RIGHT","AMBIGUOUS_RIGHT",
"NOTICE_MISSED","NOTICE_ON_TIME","CUSTOMER_PRIOR_APPROVAL","NO_PRIOR_APPROVAL","PRIOR_PAYMENT","DUPLICATE_CLAIM",
"WRONG_REVISION","WRONG_PART","WRONG_PROGRAM","WRONG_CUSTOMER","WRONG_CURRENCY","SUPERSEDED_DRAWING","SUPERSEDED_CONTRACT","ZERO_RECOVERY"}
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=CASES
        cls.base=next(x for x in cls.cases if x["change_id"]=="EC-ALPHA-001")
    def _run(self, mutate):
        c=copy.deepcopy(self.base); mutate(c); return analyze_case(c,"2026-08-28")
    def test_independent_oracle_cases(self):
        for c in self.cases:
            with self.subTest(c["change_id"]):
                r=analyze_case(c,"2026-08-28"); o=c["oracle"]
                for k in ("status","recoverable_amount","nonrecoverable_amount","unknown_amount","mitigated_amount","prior_payment_amount"):
                    self.assertEqual(r[k],o[k])
    def test_mandatory_scenario_matrix_is_complete(self):
        tags={t for c in self.cases for t in c.get("scenario_tags",[])}
        self.assertEqual(MANDATORY-tags,set())
        self.assertEqual(len(self.cases),26)
    def test_boolean_without_linked_evidence_fails_closed(self):
        def m(c):
            c["costs"][0]["evidence_refs"]=[]; c["costs"][0]["evidence_supported"]=True
        r=self._run(m); self.assertEqual(r["recoverable_amount"],30000); self.assertEqual(r["unknown_amount"],120000)
    def test_mixed_currency_fails_closed(self):
        def m(c): c["costs"][1]["currency"]="USD"
        r=self._run(m); self.assertEqual(r["status"],"UNKNOWN"); self.assertIn("MIXED_CURRENCY",r["flags"])
    def test_wrong_customer_context_fails_closed(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="change")["asserts"]["customer"]="OTHER"
        r=self._run(m); self.assertEqual(r["recoverable_amount"],0); self.assertGreater(r["unknown_amount"],0)
    def test_wrong_program_context_fails_closed(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="change")["asserts"]["program"]="OTHER"
        r=self._run(m); self.assertEqual(r["recoverable_amount"],0)
    def test_wrong_part_context_fails_closed(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="change")["asserts"]["part"]="OTHER"
        r=self._run(m); self.assertEqual(r["recoverable_amount"],0)
    def test_wrong_revision_context_fails_closed(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="revision")["asserts"]["revision_to"]="Z"
        r=self._run(m); self.assertEqual(r["recoverable_amount"],0)
    def test_cost_amount_mismatch_isolated_to_cost_line(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="cost-tooling")["asserts"]["amount"]=1
        r=self._run(m); self.assertEqual(r["recoverable_amount"],30000); self.assertEqual(r["unknown_amount"],120000)
    def test_cost_currency_mismatch_isolated_to_cost_line(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="cost-tooling")["asserts"]["currency"]="USD"
        r=self._run(m); self.assertEqual(r["recoverable_amount"],30000); self.assertEqual(r["unknown_amount"],120000)
    def test_causal_state_mismatch_fails_line_closed(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="causal-tooling")["asserts"]["causal_state"]="UNRELATED"
        r=self._run(m); self.assertEqual(r["recoverable_amount"],30000); self.assertEqual(r["unknown_amount"],120000)
    def test_zero_mitigation_still_requires_reconciliation(self):
        def m(c): c["costs"][1]["mitigation_evidence_refs"]=[]
        r=self._run(m); self.assertEqual(r["recoverable_amount"],110000); self.assertEqual(r["unknown_amount"],30000)
    def test_nonzero_mitigation_mismatch_fails_line_closed(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="mit-tooling")["asserts"]["mitigation_amount"]=0
        r=self._run(m); self.assertEqual(r["recoverable_amount"],30000); self.assertEqual(r["unknown_amount"],120000)
    def test_zero_prior_payment_still_requires_reconciliation(self):
        def m(c): c["costs"][0]["prior_payment_evidence_refs"]=[]
        r=self._run(m); self.assertEqual(r["recoverable_amount"],30000); self.assertEqual(r["unknown_amount"],120000)
    def test_nonzero_prior_payment_mismatch_fails_line_closed(self):
        legacy=next(x for x in self.cases if x["change_id"]=="EC-LEG-077"); c=copy.deepcopy(legacy)
        next(e for e in c["evidence"] if e["id"]=="pay-scrap")["asserts"]["prior_payment_amount"]=0
        r=analyze_case(c); self.assertEqual(r["recoverable_amount"],0); self.assertEqual(r["unknown_amount"],70000)
    def test_contract_state_mismatch_fails_closed(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="terms")["asserts"]["contract_state"]="UNSUPPORTED"
        r=self._run(m); self.assertEqual(r["recoverable_amount"],0); self.assertGreater(r["unknown_amount"],0)
    def test_notice_deadline_mismatch_fails_closed(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="terms")["asserts"]["notice_deadline"]="2026-09-30"
        r=self._run(m); self.assertEqual(r["recoverable_amount"],0)
    def test_notice_proof_wrong_date_fails_closed(self):
        def m(c): next(e for e in c["evidence"] if e["id"]=="notice-proof")["asserts"]["notice_sent"]="2026-08-23"
        r=self._run(m); self.assertEqual(r["recoverable_amount"],0); self.assertIn("NOTICE_PROOF_MISSING",r["flags"])
    def test_prior_approval_proof_mismatch_fails_closed(self):
        c=copy.deepcopy(next(x for x in self.cases if x["change_id"]=="EC-APPROVAL"))
        next(e for e in c["evidence"] if e["id"]=="approval-proof")["asserts"]["prior_approval_obtained"]=False
        r=analyze_case(c); self.assertEqual(r["recoverable_amount"],0); self.assertEqual(r["status"],"UNKNOWN")
    def test_duplicate_evidence_id_fails_referenced_claim_closed(self):
        def m(c):
            dup=copy.deepcopy(next(e for e in c["evidence"] if e["id"]=="cost-tooling"))
            dup["asserts"]["amount"]=999
            c["evidence"].append(dup)
        r=self._run(m); self.assertIn("DUPLICATE_EVIDENCE_ID",r["flags"])
if __name__=="__main__": unittest.main()
