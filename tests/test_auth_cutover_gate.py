"""Synthetic regression for the offline ObraSignal identity cutover guard."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('auth_cutover_gate',Path(__file__).resolve().parents[1]/'scripts'/'auth_cutover_gate.py')
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
SHA='a'*40

def fixture():
    legacy={'accounts':[{'legacy_subject':'old-A','company_id':'company-A'},
                        {'legacy_subject':'old-A','company_id':'company-B'},
                        {'legacy_subject':'old-B','company_id':'company-B'}], 'expected_pairs':3}
    mapping={'mappings':[{'legacy_subject':'old-A','company_id':'company-A','neon_subject':'new-A'},
                         {'legacy_subject':'old-A','company_id':'company-B','neon_subject':'new-A'},
                         {'legacy_subject':'old-B','company_id':'company-B','neon_subject':'new-B'}], 'expected_pairs':3}
    evidence={k:True for k in gate._EVIDENCE}
    evidence['checked_commit']=SHA
    return legacy,mapping,evidence

class AuthCutoverTests(unittest.TestCase):
    def test_synthetic_complete_mapping_is_only_a_prerequisite(self):
        d=gate.evaluate(*fixture(),expected_commit=SHA)
        self.assertEqual(d['result'],'MAPPING_GATE_PASS_NOT_RELEASE_AUTHORIZATION')
        self.assertEqual(d['distinct_identities'],2)
    def test_missing_evidence_blocks(self):
        a,b,c=fixture();c['tenant_isolation']=False
        with self.assertRaisesRegex(gate.GateBlocked,'RELEASE_EVIDENCE_MISSING'):
            gate.evaluate(a,b,c,SHA)
    def test_exact_commit_gate_blocks(self):
        a,b,c=fixture()
        with self.assertRaisesRegex(gate.GateBlocked,'EXACT_COMMIT_NOT_PROVEN'):
            gate.evaluate(a,b,c,'b'*40)
    def test_missing_legacy_membership_blocks(self):
        a,b,c=fixture();a['accounts'].pop();a['expected_pairs']=2
        with self.assertRaisesRegex(gate.GateBlocked,'IDENTITY_OR_TENANT_COVERAGE_MISMATCH'):
            gate.evaluate(a,b,c,SHA)
    def test_identity_collision_blocks(self):
        a,b,c=fixture();b['mappings'][-1]['neon_subject']='new-A'
        with self.assertRaisesRegex(gate.GateBlocked,'TARGET_IDENTITY_COLLISION'):
            gate.evaluate(a,b,c,SHA)
    def test_split_legacy_identity_blocks(self):
        a,b,c=fixture();b['mappings'][1]['neon_subject']='new-C'
        with self.assertRaisesRegex(gate.GateBlocked,'LEGACY_IDENTITY_SPLIT'):
            gate.evaluate(a,b,c,SHA)
    def test_duplicate_membership_blocks(self):
        a,b,c=fixture();a['accounts'].append(a['accounts'][0].copy());a['expected_pairs']=4
        with self.assertRaisesRegex(gate.GateBlocked,'LEGACY_PAIR_DUPLICATED'):
            gate.evaluate(a,b,c,SHA)
    def test_zero_records_do_not_prove_recovery(self):
        a,b,c=fixture();a={'accounts':[],'expected_pairs':0};b={'mappings':[],'expected_pairs':0}
        with self.assertRaisesRegex(gate.GateBlocked,'NO_EXISTING_IDENTITY_PRESERVATION_PROOF'):
            gate.evaluate(a,b,c,SHA)
    def test_email_bearing_identity_field_blocked(self):
        a,b,c=fixture();a['accounts'][0]['legacy_subject']='personal@example.com'
        with self.assertRaisesRegex(gate.GateBlocked,'INVALID_IDENTITY_RECORD'):
            gate.evaluate(a,b,c,SHA)

if __name__=='__main__': unittest.main()
