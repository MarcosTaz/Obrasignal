import unittest

from founder_control_center.wsgi import app


class WSGIEntrypointTests(unittest.TestCase):
    def test_wsgi_entrypoint_exposes_flask_app(self):
        self.assertTrue(hasattr(app, "test_client"))
        response = app.test_client().get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["truth"], "process_alive_not_global_green")


if __name__ == "__main__":
    unittest.main()
