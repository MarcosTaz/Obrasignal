import unittest
from unittest.mock import patch

import requests

from founder_control_center.adapters import GitHubAdapter
from founder_control_center.models import TruthState


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class DeploymentAdapterTests(unittest.TestCase):
    @patch("founder_control_center.adapters.requests.get")
    def test_success_status_is_green(self, get):
        get.side_effect = [
            FakeResponse(payload=[{"id": 42, "environment": "production", "sha": "deploy123"}]),
            FakeResponse(payload=[{"state": "success", "environment_url": "https://app.example.test"}]),
        ]
        state, evidence, url = GitHubAdapter(token=None).refresh_deployment("owner/public")
        self.assertEqual(state, TruthState.GREEN)
        self.assertEqual(url, "https://app.example.test")
        self.assertIn("state=success", evidence.detail)

    @patch("founder_control_center.adapters.requests.get")
    def test_private_environment_url_is_not_granted_health_check_authority(self, get):
        get.side_effect = [
            FakeResponse(payload=[{"id": 43, "environment": "production", "sha": "deploy-private"}]),
            FakeResponse(payload=[{"state": "success", "environment_url": "http://127.0.0.1:8080"}]),
        ]
        state, evidence, url = GitHubAdapter(token=None).refresh_deployment("owner/public")
        self.assertEqual(state, TruthState.GREEN)
        self.assertIsNone(url)
        self.assertIn("environment_url rejected", evidence.detail)
        self.assertNotEqual(evidence.url, "http://127.0.0.1:8080")

    @patch("founder_control_center.adapters.requests.get")
    def test_malformed_deployment_id_fails_closed_before_status_request(self, get):
        get.return_value = FakeResponse(payload=[{"id": "../../repos/other", "environment": "production", "sha": "deploy-malformed"}])
        state, evidence, url = GitHubAdapter(token=None).refresh_deployment("owner/public")
        self.assertEqual(state, TruthState.UNKNOWN)
        self.assertIsNone(url)
        self.assertIn("invalid deployment id", evidence.detail)
        self.assertEqual(get.call_count, 1)

    @patch("founder_control_center.adapters.requests.get")
    def test_no_deployment_is_unknown(self, get):
        get.return_value = FakeResponse(payload=[])
        state, _, url = GitHubAdapter(token=None).refresh_deployment("owner/public")
        self.assertEqual(state, TruthState.UNKNOWN)
        self.assertIsNone(url)

    @patch("founder_control_center.adapters.requests.get")
    def test_inaccessible_deployment_source_is_unknown(self, get):
        get.return_value = FakeResponse(status_code=403)
        state, evidence, url = GitHubAdapter(token="configured-but-denied").refresh_deployment("owner/private")
        self.assertEqual(state, TruthState.UNKNOWN)
        self.assertIsNone(url)
        self.assertIn("inaccessible", evidence.detail)

    @patch("founder_control_center.adapters.requests.get")
    def test_deployment_source_transport_failure_is_unknown(self, get):
        get.side_effect = requests.ConnectionError("offline")
        state, evidence, url = GitHubAdapter(token=None).refresh_deployment("owner/public")
        self.assertEqual(state, TruthState.UNKNOWN)
        self.assertIsNone(url)
        self.assertIn("remains UNKNOWN", evidence.detail)

    @patch("founder_control_center.adapters.requests.get")
    def test_failure_status_is_degraded(self, get):
        get.side_effect = [
            FakeResponse(payload=[{"id": 7, "environment": "production", "sha": "deploybad"}]),
            FakeResponse(payload=[{"state": "failure"}]),
        ]
        state, _, _ = GitHubAdapter(token=None).refresh_deployment("owner/public")
        self.assertEqual(state, TruthState.DEGRADED)


if __name__ == "__main__":
    unittest.main()
