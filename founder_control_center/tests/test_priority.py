import unittest

from founder_control_center.models import ApplicationState, CompanyManifest, RepositoryState, TruthState
from founder_control_center.ranking import highest_value_actions, rank_company


class PriorityTests(unittest.TestCase):
    def test_degraded_ci_is_critical_action(self):
        company = CompanyManifest(
            id="ci-risk",
            name="CI Risk",
            mission="Test ranking semantics.",
            status="ACTIVE",
            stage="build",
            repository=RepositoryState(full_name="owner/repo", commit="abc", ci=TruthState.DEGRADED),
        )
        action = highest_value_actions([company], 1)[0]
        self.assertEqual(action["urgency"], "critical")
        self.assertEqual(action["action"], "Diagnose failing repository CI")
        self.assertIn("repository CI degraded", rank_company(company).reasons)

    def test_degraded_deployment_precedes_noncritical_work(self):
        company = CompanyManifest(
            id="deploy-risk",
            name="Deployment Risk",
            mission="Test deployment priority.",
            status="ACTIVE",
            stage="build",
            repository=RepositoryState(full_name="owner/repo", commit="abc", ci=TruthState.GREEN),
            application=ApplicationState(deployment=TruthState.DEGRADED, health=TruthState.UNKNOWN),
        )
        action = highest_value_actions([company], 1)[0]
        self.assertEqual(action["urgency"], "critical")
        self.assertEqual(action["action"], "Diagnose degraded deployment before any release action")


if __name__ == "__main__":
    unittest.main()
