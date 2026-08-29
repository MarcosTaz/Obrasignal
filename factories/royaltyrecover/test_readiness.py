import tempfile
import unittest
from pathlib import Path

from application import create_full_app
from repository import RoyaltyRepository, SQLITE_BUSY_TIMEOUT_MS


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "pilot.db")
        self.repo = RoyaltyRepository.file(self.db_path)
        self.repo.ensure_organization("ORG-A", "Alpha", "system")
        app = create_full_app(api_keys={"ORG-A": "secret"}, repository=self.repo)
        app.testing = True
        self.client = app.test_client()
        self.auth = {"X-RoyaltyRecover-API-Key": "secret"}

    def tearDown(self):
        self.repo.close()
        self.tempdir.cleanup()

    def test_readiness_is_protected(self):
        self.assertEqual(self.client.get("/api/v1/readiness").status_code, 401)

    def test_file_repository_uses_pilot_safety_pragmas(self):
        response = self.client.get("/api/v1/readiness", headers=self.auth)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ready"])
        self.assertEqual(data["database_integrity"], "ok")
        self.assertEqual(data["foreign_key_violation_count"], 0)
        self.assertEqual(data["journal_mode"].lower(), "wal")
        self.assertEqual(data["busy_timeout_ms"], SQLITE_BUSY_TIMEOUT_MS)
        self.assertFalse(data["claim_generation"])


if __name__ == "__main__":
    unittest.main()
