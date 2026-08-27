import os
import tempfile
import unittest

_tmp = tempfile.NamedTemporaryFile(prefix="fcc-auth-", suffix=".db", delete=False)
_tmp.close()
os.environ["FCC_DB"] = _tmp.name
os.environ["FCC_SECURE_COOKIE"] = "0"

from founder_control_center.app import create_app


class AuthTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("FCC_ADMIN_TOKEN", None)

    def test_api_fails_closed_without_authentication(self):
        app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False})
        client = app.test_client()
        response = client.get("/api/companies")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "authentication_required")

    def test_login_fails_closed_when_admin_token_is_unconfigured(self):
        os.environ.pop("FCC_ADMIN_TOKEN", None)
        app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False})
        response = app.test_client().post("/login", data={"token": "anything"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"fails closed", response.data)

    def test_valid_admin_token_creates_private_session(self):
        os.environ["FCC_ADMIN_TOKEN"] = "test-only-secret"
        app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False, "SECRET_KEY": "test-session-secret"})
        client = app.test_client()
        response = client.post("/login", data={"token": "test-only-secret"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Portfolio", response.data)
        self.assertEqual(client.get("/api/companies").status_code, 200)


if __name__ == "__main__":
    unittest.main()
