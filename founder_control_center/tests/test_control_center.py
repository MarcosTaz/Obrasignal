import os
import tempfile
import unittest

os.environ.setdefault("FCC_SECURE_COOKIE", "0")
_tmp = tempfile.NamedTemporaryFile(prefix="fcc-test-", suffix=".db", delete=False)
_tmp.close()
os.environ["FCC_DB"] = _tmp.name

from founder_control_center.actions import execute
from founder_control_center.app import create_app
from founder_control_center.models import TruthState
from founder_control_center.ranking import highest_value_actions, rank_portfolio
from founder_control_center.registry import get_company, list_companies


class ControlCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()

    def test_all_known_companies_visible_from_day_one(self):
        ids = {c.id for c in list_companies()}
        expected = {"obrasignal", "k3-fatality", "revenue-recovery", "billionaire-search", "black-leaf-tattoos", "money-leakage-auditor", "contract-os", "founder-control-center"}
        self.assertTrue(expected.issubset(ids))

    def test_unknown_revenue_stays_unknown(self):
        company = get_company("obrasignal")
        self.assertEqual(company.revenue.state, TruthState.UNKNOWN)
        self.assertIsNone(company.revenue.value)

    def test_ceo_ranking_exposes_uncertainty(self):
        ranks = rank_portfolio(list_companies())
        self.assertTrue(ranks)
        self.assertTrue(all(0 <= r.uncertainty <= 1 for r in ranks))
        self.assertTrue(any(r.uncertainty > 0 for r in ranks))

    def test_portfolio_action_center_exists(self):
        items = highest_value_actions(list_companies())
        self.assertTrue(items)
        self.assertTrue(all("uncertainty" in x and "owner_boundary" in x for x in items))

    def test_red_action_is_blocked(self):
        body, status = execute("delete_customer_data", "obrasignal", {})
        self.assertEqual(status, 403)
        self.assertEqual(body["state"], "OWNER_ONLY")

    def test_yellow_action_requires_approval(self):
        body, status = execute("prepare_deployment", "obrasignal", {})
        self.assertEqual(status, 202)
        self.assertEqual(body["state"], "APPROVAL_REQUIRED")

    def test_green_state_update_executes(self):
        body, status = execute("update_factory_state", "founder-control-center", {"active": "Run tests"})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_health_does_not_claim_global_green(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["truth"], "process_alive_not_global_green")

    def test_dashboard_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Founder Control Center", response.data)
        self.assertIn(b"ObraSignal", response.data)


if __name__ == "__main__":
    unittest.main()
