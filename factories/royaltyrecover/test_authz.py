import unittest

from authz import CredentialRegistry, role_allows


class AuthorizationTests(unittest.TestCase):
    def test_explicit_roles_are_preserved(self):
        registry = CredentialRegistry.from_config({"keys": [
            {"key_id": "a", "organization_id": "ORG-1", "secret": "analyst", "role": "ANALYST"},
            {"key_id": "r", "organization_id": "ORG-1", "secret": "reviewer", "role": "REVIEWER"},
            {"key_id": "x", "organization_id": "ORG-2", "secret": "admin", "role": "ADMIN"},
        ]})
        self.assertEqual(registry.authenticate("analyst").role, "ANALYST")
        self.assertEqual(registry.authenticate("reviewer").role, "REVIEWER")
        self.assertEqual(registry.authenticate("admin").organization_id, "ORG-2")

    def test_legacy_mapping_never_grants_review_privilege(self):
        registry = CredentialRegistry.from_config({"ORG-1": "legacy-secret"})
        self.assertEqual(registry.authenticate("legacy-secret").role, "ANALYST")

    def test_role_hierarchy(self):
        self.assertTrue(role_allows("ANALYST", "ANALYST"))
        self.assertFalse(role_allows("ANALYST", "REVIEWER"))
        self.assertTrue(role_allows("REVIEWER", "ANALYST"))
        self.assertTrue(role_allows("ADMIN", "REVIEWER"))
        self.assertFalse(role_allows("UNKNOWN", "ANALYST"))

    def test_invalid_role_fails_closed(self):
        with self.assertRaises(ValueError):
            CredentialRegistry.from_config({"keys": [
                {"key_id": "bad", "organization_id": "ORG-1", "secret": "s", "role": "OWNER"}
            ]})


if __name__ == "__main__":
    unittest.main()
