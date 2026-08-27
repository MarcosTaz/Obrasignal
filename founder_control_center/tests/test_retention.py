import unittest

from founder_control_center.models import CompanyManifest
from founder_control_center.registry import list_company_history, save_company
from founder_control_center.retention import DEFAULT_SNAPSHOT_RETENTION, install_snapshot_retention


class SnapshotRetentionTests(unittest.TestCase):
    def test_retention_keeps_only_newest_snapshots(self):
        company = CompanyManifest(
            id="retention-company",
            name="Retention Company",
            mission="Prove operational snapshots do not grow without bound.",
        )
        save_company(company)
        try:
            self.assertEqual(install_snapshot_retention(10), 10)
            for index in range(15):
                company.active = f"state-{index}"
                save_company(company)
            history = list_company_history(company.id, 200)
            self.assertEqual(len(history), 10)
            self.assertEqual(history[0]["active"], "state-14")
            self.assertEqual(history[-1]["active"], "state-5")
        finally:
            self.assertEqual(install_snapshot_retention(), DEFAULT_SNAPSHOT_RETENTION)


if __name__ == "__main__":
    unittest.main()
