import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from store import CaseStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.tmp.cleanup()

    def _case(self, tenant, change_id="EC-1", amount=100):
        return {
            "tenant_id": tenant,
            "change_id": change_id,
            "baseline_verified": True,
            "revision_verified": True,
            "costs": [{"amount": amount, "currency": "EUR", "evidence_supported": True, "cost_verified": True, "causal_state": "DIRECTLY_CAUSED"}],
            "entitlement": {"contract_state": "CONTRACTUALLY_SUPPORTED", "notice_required": False},
        }

    def test_versions_are_append_only_and_returned_in_order(self):
        self.store.save_case("A", self._case("A", amount=100))
        self.store.save_case("A", self._case("A", amount=200))
        hist = self.store.history("A", "EC-1")
        self.assertEqual([x["version"] for x in hist], [1, 2])
        self.assertEqual(hist[0]["payload"]["costs"][0]["amount"], 100)
        self.assertEqual(hist[1]["payload"]["costs"][0]["amount"], 200)

    def test_cross_tenant_read_is_isolated(self):
        self.store.save_case("A", self._case("A", amount=100))
        self.store.save_case("B", self._case("B", amount=900))
        self.assertEqual(self.store.latest_case("A", "EC-1")["payload"]["costs"][0]["amount"], 100)
        self.assertEqual(self.store.latest_case("B", "EC-1")["payload"]["costs"][0]["amount"], 900)
        self.assertEqual(len(self.store.history("A", "EC-1")), 1)

    def test_tenant_mismatch_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.store.save_case("A", self._case("B"))

    def test_analysis_requires_case_in_same_tenant(self):
        meta = self.store.save_case("A", self._case("A"))
        self.store.save_analysis("A", "EC-1", meta["version"], {"status": "RECOVERABLE"})
        self.assertEqual(len(self.store.analysis_history("A", "EC-1")), 1)
        with self.assertRaises(ValueError):
            self.store.save_analysis("B", "EC-1", meta["version"], {"status": "RECOVERABLE"})

    def test_backup_restore_preserves_history(self):
        self.store.save_case("A", self._case("A", amount=100))
        backup = Path(self.tmp.name) / "backup.db"
        self.store.backup_to(backup)
        self.store.save_case("A", self._case("A", amount=200))
        self.assertEqual(len(self.store.history("A", "EC-1")), 2)
        self.store.restore_from(backup)
        hist = self.store.history("A", "EC-1")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["payload"]["costs"][0]["amount"], 100)
        self.assertTrue(self.store.integrity_check())

    def test_concurrent_appends_do_not_lose_versions(self):
        def save(i):
            return self.store.save_case("A", self._case("A", amount=100+i))["version"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            versions = sorted(pool.map(save, range(12)))
        self.assertEqual(versions, list(range(1, 13)))
        hist = self.store.history("A", "EC-1")
        self.assertEqual(len(hist), 12)
        self.assertEqual([x["version"] for x in hist], list(range(1, 13)))

    def test_restart_preserves_history(self):
        self.store.save_case("A", self._case("A", amount=321))
        reopened = CaseStore(self.store.path)
        latest = reopened.latest_case("A", "EC-1")
        self.assertEqual(latest["payload"]["costs"][0]["amount"], 321)

    def test_atomic_evaluated_case_persists_case_and_analysis_together(self):
        payload = self._case("A", amount=777)
        analysis = {"tenant_id":"A", "change_id":"EC-1", "status":"RECOVERABLE"}
        meta = self.store.save_evaluated_case("A", payload, analysis)
        self.assertEqual(meta["saved"]["version"], 1)
        self.assertEqual(meta["analysis_saved"]["case_version"], 1)
        self.assertEqual(len(self.store.history("A", "EC-1")), 1)
        self.assertEqual(len(self.store.analysis_history("A", "EC-1")), 1)

    def test_atomic_evaluated_case_rejects_scope_mismatch_without_partial_write(self):
        payload = self._case("A", amount=777)
        analysis = {"tenant_id":"B", "change_id":"EC-1", "status":"RECOVERABLE"}
        with self.assertRaises(ValueError):
            self.store.save_evaluated_case("A", payload, analysis)
        self.assertEqual(self.store.history("A", "EC-1"), [])
        self.assertEqual(self.store.analysis_history("A", "EC-1"), [])


if __name__ == "__main__":
    unittest.main()
