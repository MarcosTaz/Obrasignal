import unittest

from founder_control_center.app import create_app
from founder_control_center.registry import get_company
from founder_control_center.sources import risk_current_state, source_summary


class RiskTruthUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()

    def test_context_seed_high_risk_is_not_current_operational_truth(self):
        company = get_company("founder-control-center")
        risk = next(item for item in company.risks if item.severity == "CRITICAL")
        self.assertEqual(risk_current_state(risk).value, "UNKNOWN")
        summary = source_summary(company)
        view = next(item for item in summary["risks"] if item["title"] == risk.title)
        self.assertEqual(view["severity"], "CRITICAL")
        self.assertEqual(view["current_truth"], "UNKNOWN")
        self.assertEqual(view["source_kind"], "context_seed")

    def test_company_page_labels_context_risk_current_truth_unknown(self):
        response = self.client.get("/company/founder-control-center")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"CRITICAL", response.data)
        self.assertIn(b"CURRENT UNKNOWN", response.data)
        self.assertIn(b"context_seed", response.data)

    def test_risk_api_separates_severity_from_current_truth(self):
        response = self.client.get("/api/companies/founder-control-center/risks")
        self.assertEqual(response.status_code, 200)
        risks = response.get_json()["risks"]
        critical = next(item for item in risks if item["severity"] == "CRITICAL")
        self.assertEqual(critical["current_truth"], "UNKNOWN")
        self.assertEqual(critical["source_kind"], "context_seed")
        self.assertNotIn("evidence", critical)

    def test_company_apis_use_same_risk_truth_projection(self):
        detail = self.client.get("/api/companies/founder-control-center").get_json()
        critical = next(item for item in detail["risks"] if item["severity"] == "CRITICAL")
        self.assertEqual(critical["current_truth"], "UNKNOWN")
        self.assertEqual(critical["source_kind"], "context_seed")

        portfolio = self.client.get("/api/companies").get_json()["companies"]
        company = next(item for item in portfolio if item["id"] == "founder-control-center")
        critical = next(item for item in company["risks"] if item["severity"] == "CRITICAL")
        self.assertEqual(critical["current_truth"], "UNKNOWN")
        self.assertEqual(critical["source_kind"], "context_seed")


if __name__ == "__main__":
    unittest.main()
