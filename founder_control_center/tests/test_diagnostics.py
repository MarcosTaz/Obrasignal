import unittest
from unittest.mock import patch

from founder_control_center.actions import execute
from founder_control_center.models import Evidence, RepositoryState, TruthState
from founder_control_center.registry import get_company, now_iso


class DiagnosticsTests(unittest.TestCase):
    @patch("founder_control_center.actions.HealthAdapter")
    @patch("founder_control_center.actions.GitHubAdapter")
    def test_refresh_keeps_repo_deployment_and_health_truth_separate(self, github_cls, health_cls):
        observed_at = now_iso()
        github = github_cls.return_value
        github.refresh_repo.return_value = RepositoryState(
            full_name="MarcosTaz/Obrasignal",
            branch="main",
            commit="diagnostic-sha",
            ci=TruthState.GREEN,
            evidence=Evidence("ci:repo", observed_at, 3600, "test"),
        )
        github.refresh_deployment.return_value = (
            TruthState.GREEN,
            Evidence("ci:deployment", observed_at, 3600, "test"),
            "https://app.example.test",
        )
        health_cls.return_value.refresh.return_value = (
            TruthState.GREEN,
            Evidence("ci:health", observed_at, 3600, "test"),
        )

        body, status = execute("refresh_diagnostics", "obrasignal", {})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["changes"], ["repository", "deployment", "application_health"])

        company = get_company("obrasignal")
        self.assertEqual(company.repository.commit, "diagnostic-sha")
        self.assertEqual(company.repository.ci, TruthState.GREEN)
        self.assertEqual(company.application.deployment, TruthState.GREEN)
        self.assertEqual(company.application.health, TruthState.GREEN)
        self.assertEqual(company.application.url, "https://app.example.test")
        self.assertEqual(company.application.deployment_evidence.source, "ci:deployment")
        self.assertEqual(company.application.health_evidence.source, "ci:health")
        health_cls.return_value.refresh.assert_called_once_with("https://app.example.test/health")


if __name__ == "__main__":
    unittest.main()
