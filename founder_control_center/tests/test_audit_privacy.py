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

    def test_green_state_update_audit_records_shape_not_material_values(self):
        payload = {
            "active": "private internal execution note",
            "next": "private next step",
            "wait": "private blocker detail",
        }
        body, status = execute("update_factory_state", "founder-control-center", payload)
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        event = next(item for item in list_audit(20) if item["action"] == "update_factory_state")
        source_data = event["source_data"]
        self.assertIn("changed_fields", source_data)
        self.assertIn("payload_keys", source_data)
        self.assertNotIn("private internal execution note", source_data)
        self.assertNotIn("private next step", source_data)
        self.assertNotIn("private blocker detail", source_data)


if __name__ == "__main__":
    unittest.main()
