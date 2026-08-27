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
        os.environ.pop("FCC_SESSION_SECRET", None)

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

    def test_login_fails_closed_when_admin_token_is_too_weak(self):
        os.environ["FCC_ADMIN_TOKEN"] = "short"
        app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False})
        response = app.test_client().post("/login", data={"token": "short"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"too weak", response.data)
        self.assertNotEqual(response.status_code, 302)

    def test_login_fails_closed_without_session_secret_outside_test_mode(self):
        os.environ["FCC_ADMIN_TOKEN"] = "test-only-secret"
        os.environ.pop("FCC_SESSION_SECRET", None)
        app = create_app({"SESSION_COOKIE_SECURE": False})
        response = app.test_client().post("/login", data={"token": "test-only-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"FCC_SESSION_SECRET", response.data)

    def test_login_fails_closed_with_weak_session_secret_outside_test_mode(self):
        os.environ["FCC_ADMIN_TOKEN"] = "test-only-secret"
        os.environ["FCC_SESSION_SECRET"] = "too-short"
        app = create_app({"SESSION_COOKIE_SECURE": False})
        response = app.test_client().post("/login", data={"token": "test-only-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"too weak", response.data)

    def test_valid_admin_token_creates_private_session(self):
        os.environ["FCC_ADMIN_TOKEN"] = "test-only-secret"
        app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False, "SECRET_KEY": "test-session-secret"})
        client = app.test_client()
        response = client.post("/login", data={"token": "test-only-secret"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Portfolio", response.data)
        self.assertEqual(client.get("/api/companies").status_code, 200)

    def test_founder_mutation_requires_csrf_after_login(self):
        os.environ["FCC_ADMIN_TOKEN"] = "test-only-secret"
        app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False, "SECRET_KEY": "csrf-session-secret"})
        client = app.test_client()
        login = client.post("/login", data={"token": "test-only-secret"})
        self.assertEqual(login.status_code, 302)
        missing = client.post("/api/actions/update_factory_state/execute", json={"company_id": "founder-control-center", "payload": {"active": "CSRF test"}})
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(missing.get_json()["error"], "csrf_validation_failed")
        with client.session_transaction() as session_state:
            csrf = session_state["csrf_token"]
        accepted = client.post(
            "/api/actions/update_factory_state/execute",
            json={"company_id": "founder-control-center", "payload": {"active": "CSRF test"}},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.get_json()["ok"])

    def test_security_headers_are_present(self):
        app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False})
        response = app.test_client().get("/health")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("default-src 'self'", response.headers.get("Content-Security-Policy", ""))
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")


if __name__ == "__main__":
    unittest.main()
