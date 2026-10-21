import unittest

from factory_cloud.factory_switchboard import load_switchboard, start_packet


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

    def test_historical_changeledger_alias_resolves_to_scopeledger(self) -> None:
        packet = start_packet("changeledger", load_switchboard())
        self.assertEqual(packet["requested_factory_id"], "changeledger")
        self.assertEqual(packet["factory_id"], "scopeledger")
        self.assertEqual(packet["name"], "ScopeLedger")

    def test_unknown_factory_fails_closed(self) -> None:
        with self.assertRaises(Exception):
            start_packet("not-registered", load_switchboard())


if __name__ == "__main__":
    unittest.main()
