import json
import subprocess
import unittest
from pathlib import Path

from factory_cloud.process_adapter import ProcessAdapterConfig


ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
SYSTEMD = RUNTIME / "systemd"


class RuntimeProvisioningTests(unittest.TestCase):
    def test_concrete_obrasignal_adapter_is_app_scoped_and_contains_no_secret_material(self):
        path = RUNTIME / "obrasignal-adapter.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        config = ProcessAdapterConfig.load(path, expected_app_id="obrasignal")

        self.assertEqual(config.app_id, "obrasignal")
        self.assertEqual(config.mode, "repository_safe_execution")
        self.assertEqual(str(config.workspace), "/srv/factory-cloud/apps/obrasignal")
        self.assertEqual(config.command, (
            "/usr/bin/python3",
            "/opt/factory-cloud/current/factory_cloud/obrasignal_agent.py",
        ))
        encoded = json.dumps(payload).lower()
        for forbidden in ("token", "password", "secret", "customer", "billing"):
            self.assertNotIn(forbidden, encoded)

    def test_host_shell_artifacts_are_syntactically_valid(self):
        for path in (SYSTEMD / "install.sh", SYSTEMD / "prepare-obrasignal-workspace.sh"):
            completed = subprocess.run(
                ["bash", "-n", str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_workspace_preparer_is_fail_closed_and_never_hard_resets(self):
        text = (SYSTEMD / "prepare-obrasignal-workspace.sh").read_text(encoding="utf-8")
        self.assertIn('status --porcelain', text)
        self.assertIn('checkout --detach "${EXPECTED_HEAD}"', text)
        self.assertIn('factory_cloud/apps.json', text)
        self.assertIn('canonical source truth is not verified', text)
        self.assertNotIn("reset --hard", text)
        self.assertNotIn("git clean", text)
        self.assertNotIn("k3-fatality", text.lower())

    def test_installer_defaults_to_obrasignal_only_and_uses_private_app_config_group(self):
        text = (SYSTEMD / "install.sh").read_text(encoding="utf-8")
        self.assertIn('APPS="${APPS:-obrasignal}"', text)
        self.assertIn('install -o root -g "${user}" -m 0640', text)
        self.assertIn('prepare-obrasignal-workspace.sh', text)
        self.assertNotIn('APPS="${APPS:-obrasignal k3-fatality}"', text)

    def test_systemd_worker_still_keeps_per_app_identity_and_adapter_config(self):
        text = (SYSTEMD / "factory-cloud-app@.service").read_text(encoding="utf-8")
        self.assertIn("User=factory-cloud-%i", text)
        self.assertIn("Group=factory-cloud-%i", text)
        self.assertIn("SupplementaryGroups=factory-cloud", text)
        self.assertIn("UMask=0007", text)
        self.assertIn("--adapter-config /etc/factory-cloud/apps/%i.json", text)
        self.assertIn("NoNewPrivileges=true", text)


if __name__ == "__main__":
    unittest.main()
