import json
import unittest
from pathlib import Path

from engine import analyze_case

ROOT = Path(__file__).resolve().parent


class OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((ROOT / "synthetic_cases.json").read_text())

    def test_independent_oracle_cases(self):
        for case in self.cases:
            with self.subTest(change_id=case["change_id"]):
                result = analyze_case(case, "2026-08-28")
                oracle = case["oracle"]
                self.assertEqual(result["status"], oracle["status"])
                self.assertEqual(result["recoverable_amount"], oracle["recoverable_amount"])
                self.assertEqual(result["nonrecoverable_amount"], oracle["nonrecoverable_amount"])
                self.assertEqual(result["unknown_amount"], oracle["unknown_amount"])
                self.assertEqual(result["mitigated_amount"], oracle.get("mitigated_amount", 0.0))
                self.assertEqual(result["prior_payment_amount"], oracle.get("prior_payment_amount", 0.0))

    def test_unverified_cost_fails_closed(self):
        case = {
            "tenant_id": "x",
            "change_id": "x1",
            "baseline_verified": True,
            "revision_verified": True,
            "costs": [{"amount": 1000, "currency":"EUR", "evidence_supported": False, "cost_verified": False, "causal_state":"DIRECTLY_CAUSED"}],
            "entitlement": {"contract_state":"CONTRACTUALLY_SUPPORTED", "notice_required": False},
        }
        result = analyze_case(case)
        self.assertEqual(result["recoverable_amount"], 0.0)
        self.assertEqual(result["unknown_amount"], 1000.0)
        self.assertIn("UNVERIFIED_COST", result["flags"])

    def test_mixed_currency_fails_closed(self):
        case = {
            "tenant_id": "x",
            "change_id": "x2",
            "baseline_verified": True,
            "revision_verified": True,
            "costs": [
                {"amount": 1000, "currency":"EUR", "evidence_supported": True, "cost_verified": True, "causal_state":"DIRECTLY_CAUSED"},
                {"amount": 1000, "currency":"USD", "evidence_supported": True, "cost_verified": True, "causal_state":"DIRECTLY_CAUSED"}
            ],
            "entitlement": {"contract_state":"CONTRACTUALLY_SUPPORTED", "notice_required": False},
        }
        result = analyze_case(case)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIn("MIXED_CURRENCY", result["flags"])

    def test_notice_not_sent_before_future_deadline_is_not_verified_recovery(self):
        case = {
            "tenant_id": "x",
            "change_id": "x3",
            "baseline_verified": True,
            "revision_verified": True,
            "change_evidence_refs": ["change"],
            "baseline_evidence_refs": ["baseline"],
            "revision_evidence_refs": ["revision"],
            "evidence": [
                {"id":"change","type":"CHANGE_NOTICE","verified":True},
                {"id":"baseline","type":"BASELINE_DOCUMENT","verified":True},
                {"id":"revision","type":"REVISION_DOCUMENT","verified":True},
                {"id":"cost","type":"COST_RECORD","verified":True},
                {"id":"terms","type":"CONTRACT_OR_COMMERCIAL_TERMS","verified":True},
            ],
            "costs": [{"id":"c1", "amount": 1000, "currency":"EUR", "evidence_supported": True, "cost_verified": True, "evidence_refs":["cost"], "causal_state":"DIRECTLY_CAUSED", "causality_evidence_refs":["change","cost"]}],
            "entitlement": {"contract_state":"CONTRACTUALLY_SUPPORTED", "basis_evidence_refs":["terms"], "notice_required": True, "notice_deadline":"2026-09-01", "notice_sent": None},
        }
        result = analyze_case(case, "2026-08-28")
        self.assertEqual(result["recoverable_amount"], 0.0)
        self.assertEqual(result["unknown_amount"], 1000.0)
        self.assertIn("NOTICE_NOT_SENT_AT_RISK", result["flags"])

    def test_evidence_boolean_without_linked_evidence_fails_closed(self):
        case = {
            "tenant_id": "x",
            "change_id": "x4",
            "baseline_verified": True,
            "revision_verified": True,
            "costs": [{"id":"c1", "amount": 5000, "currency":"EUR", "evidence_supported": True, "cost_verified": True, "causal_state":"DIRECTLY_CAUSED"}],
            "entitlement": {"contract_state":"CONTRACTUALLY_SUPPORTED", "notice_required": False},
        }
        result = analyze_case(case)
        self.assertEqual(result["recoverable_amount"], 0.0)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIn("UNVERIFIED_COST", result["flags"])
        self.assertTrue(result["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
