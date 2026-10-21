import unittest
from pathlib import Path


class BuildContextPolicyTests(unittest.TestCase):
    def test_dockerfile_specific_context_is_allowlisted(self):
        policy = Path("founder_control_center/Dockerfile.dockerignore").read_text(encoding="utf-8")
        lines = {line.strip() for line in policy.splitlines() if line.strip() and not line.lstrip().startswith("#")}
        self.assertIn("**", lines)
        self.assertIn("!requirements.txt", lines)
        self.assertIn("!founder_control_center/", lines)
        self.assertIn("!founder_control_center/**", lines)
        self.assertIn("founder_control_center/.env", lines)
        self.assertIn("founder_control_center/.env.*", lines)
        self.assertIn("!founder_control_center/.env.example", lines)
        self.assertIn("founder_control_center/**/*.db", lines)


if __name__ == "__main__":
    unittest.main()
