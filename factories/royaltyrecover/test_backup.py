import tempfile
import unittest
from pathlib import Path

from backup import backup_repository, verify_backup
from repository import RoyaltyRepository


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        self.repo.ensure_organization("ORG-A", "Alpha", "system")
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tempdir.name) / "royaltyrecover.sqlite3")

    def tearDown(self):
        self.repo.close()
        self.tempdir.cleanup()

    def test_backup_is_integrity_checked_and_hash_verifiable(self):
        result = backup_repository(self.repo, self.path)
        self.assertEqual(result.integrity, "ok")
        self.assertGreaterEqual(result.table_count, 33)
        verified = verify_backup(self.path, result.sha256)
        self.assertEqual(verified.sha256, result.sha256)
        restored = RoyaltyRepository.file(self.path)
        try:
            self.assertEqual(restored.ensure_organization("ORG-A", "Alpha")["name"], "Alpha")
        finally:
            restored.close()

    def test_backup_refuses_to_overwrite_existing_file(self):
        backup_repository(self.repo, self.path)
        with self.assertRaises(FileExistsError):
            backup_repository(self.repo, self.path)

    def test_wrong_expected_hash_fails_closed(self):
        backup_repository(self.repo, self.path)
        with self.assertRaises(RuntimeError):
            verify_backup(self.path, "0" * 64)


if __name__ == "__main__":
    unittest.main()
