import unittest

from factory_cloud.factory_switchboard import grouped_portfolio_switches, list_portfolio_switches, load_switchboard, start_packet
from factory_cloud.portfolio import load_portfolio


class FactorySwitchboardTests(unittest.TestCase):
    def test_registry_is_switchboard_only(self) -> None:
        switchboard = load_switchboard()
        self.assertEqual(switchboard["scope"], "switchboard_only")
        self.assertNotIn("baton", switchboard)
        self.assertNotIn("credentials", switchboard)
        self.assertGreaterEqual(len(switchboard["factories"]), 10)

    def test_business_factory_emits_continuous_resume_signal(self) -> None:
        packet = start_packet("industrial-claims", load_switchboard())
        self.assertEqual(packet["signal"], "X")
        self.assertIn("DO NOT RESTART", packet["payload"])
        self.assertIn("NOT A STOP CONDITION", packet["payload"])
        self.assertIn("TRUE EXTERNAL BLOCKER", packet["payload"])

    def test_factory_cloud_uses_d_global_switch(self) -> None:
        packet = start_packet("factory-cloud", load_switchboard())
        self.assertEqual(packet["signal"], "D")
        self.assertTrue(packet["payload"].startswith("D — RESUME THE EXISTING FACTORY"))
        self.assertNotIn("Ω", packet["payload"])

    def test_portfolio_view_enriches_without_changing_signal(self) -> None:
        rows = list_portfolio_switches(load_switchboard(), load_portfolio())
        index = {row["factory_id"]: row for row in rows}
        self.assertEqual(index["factory-cloud"]["layer"], "control")
        self.assertEqual(index["factory-cloud"]["signal"], "D")
        self.assertEqual(index["industrial-claims"]["family"], "recovery-assurance")
        self.assertEqual(index["scopeledger"]["maturity"], "UNASSESSED")
        self.assertEqual(index["contractcredit"]["source_status"], "registered")

    def test_portfolio_view_groups_registered_factories_by_layer(self) -> None:
        rows = list_portfolio_switches(load_switchboard(), load_portfolio())
        grouped = grouped_portfolio_switches(rows)
        self.assertIn("control", grouped)
        self.assertIn("verticals", grouped)
        self.assertIn("specialists", grouped)
        ids = {row["factory_id"] for group in grouped.values() for row in group}
        registry_ids = {factory["id"] for factory in load_switchboard()["factories"]}
        self.assertEqual(ids, registry_ids)
        self.assertIn("contractcredit", ids)

    def test_unknown_factory_fails_closed(self) -> None:
        with self.assertRaises(Exception):
            start_packet("not-registered", load_switchboard())


if __name__ == "__main__":
    unittest.main()
