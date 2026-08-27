import os
import unittest
from unittest.mock import patch

import requests

from founder_control_center.adapters import GitHubAdapter
from founder_control_center.models import TruthState


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class GitHubAdapterTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("FCC_GITHUB_TOKEN", None)

    @patch("founder_control_center.adapters.requests.get")
    def test_public_repo_can_prove_green_ci_without_token(self, get):
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "abc123"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "success"}]}),
            FakeResponse(payload={"state": "success"}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.branch, "main")
        self.assertEqual(state.commit, "abc123")
        self.assertEqual(state.ci, TruthState.GREEN)

    @patch("founder_control_center.adapters.requests.get")
    def test_inaccessible_repo_without_token_stays_unknown(self, get):
        get.return_value = FakeResponse(status_code=404)
        state = GitHubAdapter(token=None).refresh_repo("owner/private")
        self.assertEqual(state.ci, TruthState.UNKNOWN)
        self.assertIsNone(state.commit)

    @patch("founder_control_center.adapters.requests.get")
    def test_inaccessible_repo_with_configured_token_stays_unknown(self, get):
        get.return_value = FakeResponse(status_code=403)
        state = GitHubAdapter(token="configured-but-denied").refresh_repo("owner/private")
        self.assertEqual(state.ci, TruthState.UNKNOWN)
        self.assertIn("credential", state.evidence.detail.lower())

    @patch("founder_control_center.adapters.requests.get")
    def test_github_source_transport_failure_does_not_claim_ci_degraded(self, get):
        get.side_effect = requests.ConnectionError("offline")
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.UNKNOWN)
        self.assertIn("remains UNKNOWN", state.evidence.detail)

    @patch("founder_control_center.adapters.requests.get")
    def test_failed_check_is_degraded(self, get):
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "bad123"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "failure"}]}),
            FakeResponse(payload={"state": "failure"}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.DEGRADED)

    @patch("founder_control_center.adapters.requests.get")
    def test_skipped_check_does_not_prove_green(self, get):
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "skip123"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "skipped"}]}),
            FakeResponse(payload={"state": "success"}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.UNKNOWN)
        self.assertIn("skipped", state.evidence.detail.lower())

    @patch("founder_control_center.adapters.requests.get")
    def test_neutral_check_does_not_prove_green(self, get):
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "neutral123"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "neutral"}]}),
            FakeResponse(payload={"state": "success"}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
