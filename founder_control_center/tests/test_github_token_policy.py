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


class GitHubTokenPolicyTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("FCC_GITHUB_TOKEN", None)

    @patch("founder_control_center.adapters.requests.get")
    def test_weak_environment_token_is_not_sent_and_public_truth_still_refreshes(self, get):
        os.environ["FCC_GITHUB_TOKEN"] = "tiny"
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "public123"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "success"}]}),
            FakeResponse(payload={"state": "success", "total_count": 1}),
        ]

        state = GitHubAdapter().refresh_repo("owner/public")

        self.assertEqual(state.ci, TruthState.GREEN)
        self.assertIsNone(GitHubAdapter().token)
        for call in get.call_args_list:
            self.assertNotIn("Authorization", call.kwargs["headers"])

    @patch("founder_control_center.adapters.requests.get")
    def test_explicit_weak_token_does_not_fall_back_to_environment_credential(self, get):
        os.environ["FCC_GITHUB_TOKEN"] = "environment-token-long-enough"
        get.side_effect = [
            FakeResponse(payload={"default_branch": "main"}),
            FakeResponse(payload={"sha": "explicit-policy"}),
            FakeResponse(payload={"check_runs": [{"status": "completed", "conclusion": "success"}]}),
            FakeResponse(payload={"state": "success", "total_count": 1}),
        ]

        adapter = GitHubAdapter(token="tiny")
        state = adapter.refresh_repo("owner/public")

        self.assertIsNone(adapter.token)
        self.assertEqual(state.ci, TruthState.GREEN)
        for call in get.call_args_list:
            self.assertNotIn("Authorization", call.kwargs["headers"])


if __name__ == "__main__":
    unittest.main()
