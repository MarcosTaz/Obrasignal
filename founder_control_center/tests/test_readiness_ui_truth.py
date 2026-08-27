import unittest

from founder_control_center.app import create_app


class ReadinessUITruthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "BYPASS_AUTH": True, "SESSION_COOKIE_SECURE": False})
        cls.client = cls.app.test_client()

    def test_dashboard_calls_readiness_configuration_not_connectivity(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"What is configured for use?", response.data)
        self.assertIn(b"configuration readiness only", response.data)
        self.assertIn(b"source connectivity is shown per company", response.data)
        self.assertNotIn(b"What is actually connected?", response.data)


if __name__ == "__main__":
    unittest.main()
