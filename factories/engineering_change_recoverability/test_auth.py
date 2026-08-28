import unittest
from auth import AuthError, bearer_tenant, issue_token, verify_token

SECRET = b"0123456789abcdef0123456789abcdef"


class AuthTests(unittest.TestCase):
    def test_valid_token_resolves_tenant(self):
        token = issue_token("tenant-A", ttl_seconds=100, now=1000, secret=SECRET)
        self.assertEqual(verify_token(token, now=1050, secret=SECRET)["tenant_id"], "tenant-A")
        self.assertEqual(bearer_tenant("Bearer " + token, now=1050, secret=SECRET), "tenant-A")

    def test_tampered_token_fails(self):
        token = issue_token("tenant-A", ttl_seconds=100, now=1000, secret=SECRET)
        body, sig = token.split(".")
        with self.assertRaises(AuthError):
            verify_token(body + "x." + sig, now=1050, secret=SECRET)

    def test_expired_token_fails(self):
        token = issue_token("tenant-A", ttl_seconds=10, now=1000, secret=SECRET)
        with self.assertRaises(AuthError):
            verify_token(token, now=1010, secret=SECRET)

    def test_missing_bearer_fails(self):
        with self.assertRaises(AuthError):
            bearer_tenant(None, now=1000, secret=SECRET)


if __name__ == "__main__":
    unittest.main()
