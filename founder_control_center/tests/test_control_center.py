import os
import tempfile
import unittest

os.environ.setdefault("FCC_SECURE_COOKIE", "0")
_tmp = tempfile.NamedTemporaryFile(prefix="fcc-test-", suffix=".db", delete=False)
_tmp.close()
os.environ["FCC_DB"] = _tmp.name

from founder_control_center.actions import execute, list_actions
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
        self.assertGreaterEqual(len(get_company("obrasignal").factories), 16)

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

    def test_yellow_action_requires_approval_without_fake_preparation(self):
        for action_id in ("prepare_deployment", "send_outreach"):
            body, status = execute(action_id, "obrasignal", {})
            self.assertEqual(status, 202)
            self.assertEqual(body["state"], "APPROVAL_REQUIRED")
            self.assertFalse(body["ok"])
            self.assertFalse(body["prepared"])
            self.assertFalse(body["executed"])

    def test_yellow_action_catalog_names_the_approval_gate(self):
        actions = {item["id"]: item for item in list_actions()}
        self.assertIn("approval gate", actions["prepare_deployment"]["label"].lower())
        self.assertIn("does not create or execute", actions["prepare_deployment"]["description"].lower())
        self.assertIn("approval gate", actions["send_outreach"]["label"].lower())
        self.assertIn("does not send", actions["send_outreach"]["description"].lower())

    def test_green_state_update_executes(self):
        body, status = execute("update_factory_state", "founder-control-center", {"active": "Run tests"})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["changed_fields"], ["active"])

    def test_green_action_company_payload_preserves_derived_risk_truth(self):
        body, status = execute(
            "update_factory_state",
            "founder-control-center",
            {"active": f"Projection regression {id(self)}"},
        )
        self.assertEqual(status, 200)
        critical = next(item for item in body["company"]["risks"] if item["severity"] == "CRITICAL")
        self.assertEqual(critical["current_truth"], "UNKNOWN")
        self.assertEqual(critical["source_kind"], "context_seed")
        self.assertNotIn("evidence", critical)

    def test_empty_state_update_is_rejected_not_fake_success(self):
        body, status = execute("update_factory_state", "founder-control-center", {})
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "state_fields_required")

    def test_noop_state_update_is_rejected_not_fake_success(self):
        current = get_company("founder-control-center")
        body, status = execute("update_factory_state", "founder-control-center", {"active": current.active})
        self.assertEqual(status, 409)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "no_state_change")

    def test_oversized_state_update_is_rejected_not_truncated(self):
        before = get_company("founder-control-center").active
        body, status = execute("update_factory_state", "founder-control-center", {"active": "A" * 501})
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "state_field_too_long")
        self.assertEqual(body["field"], "active")
        self.assertEqual(get_company("founder-control-center").active, before)

    def test_invalid_supplied_state_field_is_rejected_not_ignored(self):
        before = get_company("founder-control-center").next
        body, status = execute(
            "update_factory_state",
            "founder-control-center",
            {"active": 123, "next": "Would otherwise be accepted"},
        )
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "invalid_state_field")
        self.assertEqual(body["field"], "active")
        self.assertEqual(get_company("founder-control-center").next, before)

    def test_action_api_rejects_falsy_non_object_payloads(self):
        for payload in ([], False, 0, ""):
            response = self.client.post(
                "/api/actions/refresh_diagnostics/execute",
                json={"company_id": "founder-control-center", "payload": payload},
            )
            self.assertEqual(response.status_code, 400, repr(payload))
            self.assertEqual(response.get_json()["error"], "payload_must_be_object", repr(payload))

    def test_action_api_rejects_blank_company_id(self):
        response = self.client.post(
            "/api/actions/refresh_diagnostics/execute",
            json={"company_id": "   ", "payload": {}},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "company_id_required")

    def test_action_ui_checks_authority_before_claiming_execution(self):
        response = self.client.get("/static/app.js")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Checking action authority", response.data)
            self.assertNotIn(b"Executing\xe2\x80\xa6", response.data)
        finally:
            response.close()

    def test_health_does_not_claim_global_green(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["truth"], "process_alive_not_global_green")

    def test_dashboard_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Founder Control Center", response.data)
        self.assertIn(b"ObraSignal", response.data)

    def test_company_page_exposes_real_state_editor(self):
        response = self.client.get("/company/founder-control-center")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="stateUpdateForm"', response.data)
        self.assertIn(b"Save ACTIVE", response.data)
        self.assertNotIn(b'data-action="update_factory_state"', response.data)

    def test_normalized_company_api_surfaces(self):
        routes = ["metrics", "factory-state", "risks", "revenue", "actions"]
        for route in routes:
            response = self.client.get(f"/api/companies/obrasignal/{route}")
            self.assertEqual(response.status_code, 200, route)
            self.assertEqual(response.get_json()["company_id"], "obrasignal", route)
        revenue = self.client.get("/api/companies/obrasignal/revenue").get_json()["revenue"]
        self.assertEqual(revenue["state"], "UNKNOWN")
        self.assertIsNone(revenue["value"])


if __name__ == "__main__":
    unittest.main()
