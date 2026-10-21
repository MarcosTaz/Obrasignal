import os
import unittest
from unittest.mock import patch

import requests

from founder_control_center.adapters import GitHubAdapter
from founder_control_center.models import TruthState


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
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
            FakeResponse(payload={"state": "success", "total_count": 1}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.branch, "main")
        self.assertEqual(state.commit, "abc123")
        self.assertEqual(state.ci, TruthState.GREEN)

    @patch("founder_control_center.adapters.requests.get")
    def test_successful_checks_can_prove_green_when_no_commit_statuses_exist(self, get):
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "checks-only"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "success"}]}),
            FakeResponse(payload={"state": "pending", "total_count": 0, "statuses": []}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.GREEN)
        self.assertIn("no separate commit statuses", state.evidence.detail)

    @patch("founder_control_center.adapters.requests.get")
    def test_ambiguous_success_status_shape_cannot_green(self, get):
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "ambiguous-status"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "success"}]}),
            FakeResponse(payload={"state": "success"}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.UNKNOWN)
        self.assertIn("malformed", state.evidence.detail.lower())

    @patch("founder_control_center.adapters.requests.get")
    def test_string_total_count_cannot_green(self, get):
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "string-count"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "success"}]}),
            FakeResponse(payload={"state": "success", "total_count": "1"}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.UNKNOWN)
        self.assertIn("malformed", state.evidence.detail.lower())

    @patch("founder_control_center.adapters.requests.get")
    def test_success_status_cannot_green_when_check_source_is_unavailable(self, get):
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "partial-checks"}),
            FakeResponse(status_code=503),
            FakeResponse(payload={"state": "success", "total_count": 1}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.UNKNOWN)
        self.assertIn("inaccessible", state.evidence.detail.lower())

    @patch("founder_control_center.adapters.requests.get")
    def test_success_checks_cannot_green_when_status_source_is_unavailable(self, get):
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "partial-status"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "success"}]}),
            FakeResponse(status_code=503),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.UNKNOWN)
        self.assertIn("inaccessible", state.evidence.detail.lower())

    @patch("founder_control_center.adapters.requests.get")
    def test_malformed_repository_payload_fails_closed(self, get):
        get.return_value = FakeResponse(payload=[])
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.UNKNOWN)
        self.assertIn("safely", state.evidence.detail.lower())

    @patch("founder_control_center.adapters.requests.get")
    def test_invalid_repository_identifier_is_rejected_before_network_call(self, get):
        state = GitHubAdapter(token="server-token").refresh_repo("owner/repo/../../user")
        self.assertEqual(state.ci, TruthState.UNKNOWN)
        self.assertIn("rejected before GitHub access", state.evidence.detail)
        get.assert_not_called()

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
            FakeResponse(payload={"state": "failure", "total_count": 1}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.DEGRADED)

    @patch("founder_control_center.adapters.requests.get")
    def test_skipped_check_does_not_prove_green(self, get):
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "skip123"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "skipped"}]}),
            FakeResponse(payload={"state": "success", "total_count": 1}),
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
            FakeResponse(payload={"state": "success", "total_count": 1}),
        ]
        state = GitHubAdapter(token=None).refresh_repo("owner/public")
        self.assertEqual(state.ci, TruthState.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
