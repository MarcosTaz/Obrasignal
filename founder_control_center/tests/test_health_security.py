import unittest
from unittest.mock import patch

from founder_control_center.adapters import HealthAdapter
from founder_control_center.models import TruthState


class FakeResponse:
    def __init__(self, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


class HealthSecurityTests(unittest.TestCase):
    @patch("founder_control_center.adapters.requests.get")
    def test_private_destination_is_rejected_before_network_call(self, get):
        state, evidence = HealthAdapter().refresh("http://127.0.0.1:8080/health")
        self.assertEqual(state, TruthState.UNKNOWN)
        self.assertIn("rejected by network policy", evidence.detail)
        get.assert_not_called()

    @patch("founder_control_center.adapters.requests.get")
    def test_redirect_to_private_destination_is_rejected(self, get):
        get.return_value = FakeResponse(302, {"Location": "http://127.0.0.1/private"})
        state, evidence = HealthAdapter().refresh("https://8.8.8.8/health")
        self.assertEqual(state, TruthState.UNKNOWN)
        self.assertIn("rejected by network policy", evidence.detail)
        self.assertEqual(get.call_count, 1)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    @patch("founder_control_center.adapters.requests.get")
    def test_public_transport_success_is_not_overclaimed(self, get):
        get.return_value = FakeResponse(204)
        state, evidence = HealthAdapter().refresh("https://8.8.8.8/health")
        self.assertEqual(state, TruthState.GREEN)
        self.assertIn("transport green only", evidence.detail)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])


if __name__ == "__main__":
    unittest.main()
