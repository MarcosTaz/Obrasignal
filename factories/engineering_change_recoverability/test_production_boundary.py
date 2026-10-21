import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auth import AuthError, issue_token, require_role, verify_token
from production_security import derive_aes256_key, readiness_snapshot
from store import CaseStore


AUTH_SECRET = b"auth-secret-0123456789abcdef-0123456789"
AUDIT_SECRET = b"audit-secret-0123456789abcdef-012345678"
BACKUP_SECRET = b"backup-secret-0123456789abcdef-01234567"


class ProductionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "production.db"
        self.store = CaseStore(self.db, audit_secret=AUDIT_SECRET)

    def tearDown(self):
        self.tmp.cleanup()

    def _case(self, change_id="EC-PROD-1", amount=100):
        return {
            "tenant_id": "TENANT-A",
            "change_id": change_id,
            "baseline_verified": True,
            "revision_verified": True,
            "costs": [{
                "amount": amount,
                "currency": "EUR",
                "evidence_supported": True,
                "cost_verified": True,
                "causal_state": "DIRECTLY_CAUSED",
            }],
            "entitlement": {"contract_state": "CONTRACTUALLY_SUPPORTED", "notice_required": False},
        }

    def test_tokens_have_role_jti_and_bounded_lifetime(self):
        token = issue_token("TENANT-A", role="OWNER", ttl_seconds=600, now=1000, secret=AUTH_SECRET, jti="fixed-jti")
        principal = verify_token(token, now=1100, secret=AUTH_SECRET)
        self.assertEqual(principal["tenant_id"], "TENANT-A")
        self.assertEqual(principal["role"], "OWNER")
        self.assertEqual(principal["jti"], "fixed-jti")
        require_role(principal, "OWNER")
        with self.assertRaises(AuthError):
            require_role(principal, "ANALYST")
        with self.assertRaises(ValueError):
            issue_token("TENANT-A", ttl_seconds=90000, secret=AUTH_SECRET)

    def test_audit_chain_detects_tampering(self):
        self.store.save_case("TENANT-A", self._case())
        self.assertTrue(self.store.verify_audit_chain())
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE audit_events SET detail_json='{}' WHERE id=1")
        self.assertFalse(self.store.verify_audit_chain())

    def test_encrypted_backup_roundtrip_and_wrong_key_failure(self):
        self.store.save_case("TENANT-A", self._case(amount=100))
        key = derive_aes256_key(BACKUP_SECRET)
        backup = Path(self.tmp.name) / "backup.ece"
        self.store.backup_encrypted_to(backup, key=key)
        self.assertTrue(backup.read_bytes().startswith(b"ECEBK1"))
        self.store.save_case("TENANT-A", self._case(amount=200))
        self.assertEqual(len(self.store.history("TENANT-A", "EC-PROD-1")), 2)
        with self.assertRaises(ValueError):
            self.store.restore_encrypted_from(backup, key=b"x" * 32)
        self.store.restore_encrypted_from(backup, key=key)
        history = self.store.history("TENANT-A", "EC-PROD-1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["payload"]["costs"][0]["amount"], 100)
        self.assertTrue(self.store.verify_audit_chain())

    def test_owner_purge_removes_operational_data_but_keeps_audit(self):
        self.store.save_case("TENANT-A", self._case())
        with self.assertRaises(PermissionError):
            self.store.purge_change("TENANT-A", "EC-PROD-1", actor_role="ANALYST")
        result = self.store.purge_change("TENANT-A", "EC-PROD-1", actor_role="OWNER")
        self.assertEqual(result["case_versions"], 1)
        self.assertIsNone(self.store.latest_case("TENANT-A", "EC-PROD-1"))
        actions = [event["action"] for event in self.store.audit_history("TENANT-A")]
        self.assertEqual(actions, ["CASE_VERSION_SAVED", "CASE_PURGED"])
        self.assertTrue(self.store.verify_audit_chain())

    def test_retention_purge_is_owner_only_and_preserves_ledger(self):
        self.store.save_case("TENANT-A", self._case("OLD-1"))
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE case_versions SET created_at='2000-01-01T00:00:00+00:00' WHERE tenant_id='TENANT-A'")
        result = self.store.purge_before("TENANT-A", "2020-01-01T00:00:00+00:00", actor_role="OWNER")
        self.assertEqual(result["changes"], 1)
        self.assertIsNone(self.store.latest_case("TENANT-A", "OLD-1"))
        self.assertTrue(self.store.verify_audit_chain())

    def test_production_readiness_fails_closed_without_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            snapshot = readiness_snapshot(self.store)
        self.assertFalse(snapshot["ready"])
        self.assertTrue(snapshot["reasons"])

    def test_production_readiness_accepts_complete_secure_configuration(self):
        env = {
            "ECE_ENV": "production",
            "ECE_AUTH_SECRET": AUTH_SECRET.decode(),
            "ECE_AUDIT_SECRET": AUDIT_SECRET.decode(),
            "ECE_BACKUP_SECRET": BACKUP_SECRET.decode(),
            "ECE_MAX_BODY_BYTES": "1048576",
        }
        with patch.dict(os.environ, env, clear=True):
            snapshot = readiness_snapshot(self.store)
        self.assertTrue(snapshot["ready"], snapshot)
        self.assertTrue(snapshot["audit_enabled"])
        self.assertTrue(snapshot["database_integrity"])


if __name__ == "__main__":
    unittest.main()
