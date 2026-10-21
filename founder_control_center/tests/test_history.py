import unittest

from founder_control_center.actions import execute
from founder_control_center.app import create_app
from founder_control_center.models import CompanyManifest
from founder_control_center.registry import list_company_history, save_company


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()

    def setUp(self):
        save_company(CompanyManifest(id="history-company", name="History Company", mission="Test history.", active="First active"))

    def test_history_records_prior_and_current_state(self):
        body, status = execute("update_factory_state", "history-company", {"active": "Second active", "next": "Third step"})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        history = list_company_history("history-company", 10)
        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[0]["active"], "Second active")
        self.assertTrue(any(item["active"] == "First active" for item in history[1:]))

    def test_history_api_and_page(self):
        response = self.client.get("/api/companies/history-company/history?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["history"])
        page = self.client.get("/company/history-company")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Recent state snapshots", page.data)

    def test_invalid_history_limit_is_rejected(self):
        response = self.client.get("/api/companies/history-company/history?limit=bad")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
