import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from production_repository import ProductionRoyaltyRepository
from production_security import derive_backup_key, load_production_config, readiness_snapshot


AUDIT_SECRET = b"audit-secret-royaltyrecover-0123456789abcdef"
BACKUP_SECRET = b"backup-secret-royaltyrecover-0123456789abcdef"
ADMIN_SECRET = "admin-secret-royaltyrecover-0123456789abcdef"


class ProductionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "royalty.db"
        self.repo = ProductionRoyaltyRepository.file(str(self.db), audit_secret=AUDIT_SECRET)
        self.repo.ensure_organization("ORG-A", "Licensor A", "test:owner")
        self.licensor = self.repo.create_licensor("ORG-A", "Licensor A Ltd", "test:owner")
        self.licensee = self.repo.create_licensee("ORG-A", "Licensee A Ltd", "test:owner")

    def tearDown(self):
        self.repo.close()
        self.tmp.cleanup()

    def _agreement(self, title="Agreement A"):
        return self.repo.create_agreement(
            "ORG-A", self.licensor["id"], self.licensee["id"], title, "test:owner"
        )

    def _env(self):
        return {
            "ROYALTYRECOVER_ENV": "production",
            "ROYALTYRECOVER_DB_PATH": str(self.db),
            "ROYALTYRECOVER_AUDIT_SECRET": AUDIT_SECRET.decode(),
            "ROYALTYRECOVER_BACKUP_SECRET": BACKUP_SECRET.decode(),
            "ROYALTYRECOVER_MAX_BODY_BYTES": "4096",
            "ROYALTYRECOVER_CREDENTIALS_JSON": json.dumps({
                "keys": [{
                    "key_id": "admin-1",
                    "organization_id": "ORG-A",
                    "secret": ADMIN_SECRET,
                    "role": "ADMIN",
                }]
            }),
        }

    def test_production_config_requires_strong_independent_material(self):
        with patch.dict(os.environ, self._env(), clear=True):
            config = load_production_config()
        self.assertEqual(config.db_path, str(self.db))
        self.assertEqual(len(config.backup_key), 32)
        self.assertTrue(config.credentials.configured)
        weak = self._env()
        weak["ROYALTYRECOVER_AUDIT_SECRET"] = "short"
        with patch.dict(os.environ, weak, clear=True), self.assertRaises(RuntimeError):
            load_production_config()

    def test_audit_chain_is_tamper_evident(self):
        self.assertTrue(self.repo.verify_audit_chain())
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE audit_events SET payload_json='{""tampered"":true}' WHERE rowid=2")
        self.assertFalse(self.repo.verify_audit_chain())

    def test_encrypted_backup_restore_roundtrip_and_wrong_key_failure(self):
        agreement = self._agreement("Before backup")
        backup = Path(self.tmp.name) / "royalty.rrbak"
        key = derive_backup_key(BACKUP_SECRET)
        self.repo.backup_encrypted_to(backup, key=key)
        self.assertTrue(backup.read_bytes().startswith(b"ROYALTYRECOVER1"))
        self.repo.create_agreement(
            "ORG-A", self.licensor["id"], self.licensee["id"], "After backup", "test:owner"
        )
        with self.assertRaises(ValueError):
            self.repo.restore_encrypted_from(backup, key=b"x" * 32)
        self.repo.restore_encrypted_from(backup, key=key)
        restored = self.repo.get_agreement("ORG-A", agreement["id"])
        self.assertEqual(restored["title"], "Before backup")
        self.assertTrue(self.repo.integrity_check())
        self.assertTrue(self.repo.verify_audit_chain())

    def test_retention_purge_removes_agreement_tree_but_keeps_audit_ledger(self):
        agreement = self._agreement()
        version = self.repo.add_agreement_version(
            "ORG-A", agreement["id"], "v1", b"contract lineage only", "test:owner"
        )
        self.repo.add_evidence("ORG-A", "ROYALTY_STATEMENT", b"statement lineage only", "test:owner")
        self.repo.schedule_retention(
            "ORG-A", agreement["id"], "2026-01-01T00:00:00+00:00", "test retention", "test:owner"
        )
        result = self.repo.purge_due("ORG-A", "2026-08-31T00:00:00+00:00", "test:owner")
        self.assertEqual(result["purged_agreements"], [agreement["id"]])
        with self.assertRaises(LookupError):
            self.repo.get_agreement("ORG-A", agreement["id"])
        with self.assertRaises(LookupError):
            self.repo.get_agreement_version("ORG-A", version["id"])
        events = self.repo.list_audit_events("ORG-A")
        self.assertTrue(any(event["event_type"] == "PURGE" for event in events))
        self.assertTrue(self.repo.verify_audit_chain())

    def test_readiness_is_fail_closed_then_green(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(readiness_snapshot(self.repo)["ready"])
        with patch.dict(os.environ, self._env(), clear=True):
            snapshot = readiness_snapshot(self.repo)
        self.assertTrue(snapshot["ready"], snapshot)


if __name__ == "__main__":
    unittest.main()
