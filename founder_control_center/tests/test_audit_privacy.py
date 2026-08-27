import unittest

from founder_control_center.actions import execute
from founder_control_center.registry import list_audit


class AuditPrivacyTests(unittest.TestCase):
    def test_blocked_material_action_does_not_persist_payload_values(self):
        payload = {
            "password": "super-secret-value",
            "email": "private@example.test",
            "customer_note": "sensitive free text",
        }
        body, status = execute("delete_customer_data", "founder-control-center", payload)
        self.assertEqual(status, 403)
        self.assertEqual(body["state"], "OWNER_ONLY")
        event = next(item for item in list_audit(20) if item["action"] == "delete_customer_data")
        source_data = event["source_data"]
        self.assertIn("payload_keys", source_data)
        self.assertIn("password", source_data)
        self.assertNotIn("super-secret-value", source_data)
        self.assertNotIn("private@example.test", source_data)
        self.assertNotIn("sensitive free text", source_data)


if __name__ == "__main__":
    unittest.main()
