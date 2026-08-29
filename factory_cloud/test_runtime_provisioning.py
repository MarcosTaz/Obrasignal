import json
import subprocess
import unittest
from pathlib import Path

from factory_cloud.obrasignal_agent import ALLOWED_TASKS, TASK_COMPILE
from factory_cloud.process_adapter import ProcessAdapterConfig


ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
SYSTEMD = RUNTIME / "systemd"
CANONICAL_MAIN = "66d43f6fd51cf9cea08016dad335aaa04b711a24"
DEVELOPMENT_HEAD = "ea9f31b224ff7758bc28532acd3c5d4731971afa"
DEVELOPMENT_BRANCH = "integration/source-health-compensation-on-current-spine-20260828"


class RuntimeProvisioningTests(unittest.TestCase):
    def test_concrete_obrasignal_adapter_is_app_scoped_and_contains_no_secret_material(self):
        path = RUNTIME / "obrasignal-adapter.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        config = ProcessAdapterConfig.load(path, expected_app_id="obrasignal")
        self.assertEqual(config.app_id, "obrasignal")
        self.assertEqual(config.mode, "repository_safe_execution")
        self.assertEqual(str(config.workspace), "/srv/factory-cloud/apps/obrasignal")
        self.assertEqual(config.command, ("/usr/bin/python3", "/opt/factory-cloud/current/factory_cloud/obrasignal_agent.py"))
        encoded = json.dumps(payload).lower()
        for forbidden in ("token", "password", "secret", "customer", "billing"):
            self.assertNotIn(forbidden, encoded)

    def test_registry_separates_canonical_main_from_verified_development_execution_source(self):
        registry = json.loads((ROOT / "apps.json").read_text(encoding="utf-8"))
        apps = {item["app_id"]: item for item in registry["applications"]}
        obrasignal = apps["obrasignal"]
        k3 = apps["k3-fatality"]
        self.assertEqual(obrasignal["baton"]["active"], TASK_COMPILE)
        self.assertTrue(set(obrasignal["execution_adapter"]["allowlisted_tasks"]).issubset(ALLOWED_TASKS))
        self.assertFalse(obrasignal["execution_adapter"]["repository_mutation_capability"])
        canonical = obrasignal["source_truth"]
        execution = obrasignal["execution_source"]
        self.assertEqual(canonical["canonical_branch"], "main")
        self.assertEqual(canonical["canonical_head"], CANONICAL_MAIN)
        self.assertTrue(canonical["verified"])
        self.assertEqual(execution["repository"], canonical["repository"])
        self.assertEqual(execution["branch"], DEVELOPMENT_BRANCH)
        self.assertEqual(execution["head"], DEVELOPMENT_HEAD)
        self.assertTrue(execution["verified"])
        self.assertNotEqual(execution["head"], canonical["canonical_head"])
        self.assertIn("NONCANONICAL", execution["classification"])
        self.assertNotIn("execution_adapter", k3)
        self.assertNotIn("execution_source", k3)
        self.assertFalse(k3["source_truth"]["verified_source"])
        self.assertEqual(k3["activation"]["mode"], "read_only_until_source_resolved")

    def test_host_shell_artifacts_are_syntactically_valid(self):
        for path in (SYSTEMD / "install.sh", SYSTEMD / "prepare-obrasignal-workspace.sh"):
            completed = subprocess.run(["bash", "-n", str(path)], text=True, capture_output=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_workspace_preparer_targets_execution_source_and_never_hard_resets(self):
        text = (SYSTEMD / "prepare-obrasignal-workspace.sh").read_text(encoding="utf-8")
        self.assertIn('status --porcelain', text)
        self.assertIn('execution_source', text)
        self.assertIn('fetch origin "${EXECUTION_BRANCH}"', text)
        self.assertIn('checkout --detach "${EXPECTED_HEAD}"', text)
        self.assertIn('factory_cloud/apps.json', text)
        self.assertIn('canonical source truth is not verified', text)
        self.assertIn('execution source is not verified', text)
        self.assertIn('registered execution head', text)
        self.assertNotIn("reset --hard", text)
        self.assertNotIn("git clean", text)
        self.assertNotIn("k3-fatality", text.lower())

    def test_installer_defaults_to_obrasignal_only_and_provisions_secret_separated_queue_group(self):
        text = (SYSTEMD / "install.sh").read_text(encoding="utf-8")
        self.assertIn('APPS="${APPS:-obrasignal}"', text)
        self.assertIn('QUEUE_DIR="${QUEUE_DIR:-${STATE_DIR}/queues}"', text)
        self.assertIn('queue_group="factory-cloud-queue-${app}"', text)
        self.assertIn('usermod -a -G "${queue_group}" factory-cloud-control', text)
        self.assertIn('usermod -a -G "${queue_group}" "${user}"', text)
        self.assertIn('install -d -o factory-cloud-control -g "${queue_group}" -m 2770 "${QUEUE_DIR}/${app}"', text)
        self.assertIn('install -o root -g "${user}" -m 0640', text)
        self.assertIn('prepare-obrasignal-workspace.sh', text)
        self.assertNotIn('--groups factory-cloud', text)
        self.assertNotIn('usermod -a -G factory-cloud "${user}"', text)
        self.assertNotIn('usermod -a -G "${user}" factory-cloud-control', text)
        self.assertIn('still belongs to legacy shared group factory-cloud', text)
        self.assertNotIn('APPS="${APPS:-obrasignal k3-fatality}"', text)

    def test_installer_refuses_to_abandon_unconsumed_legacy_jobs(self):
        text = (SYSTEMD / "install.sh").read_text(encoding="utf-8")
        self.assertIn('mode=ro', text)
        self.assertIn("name='worker_jobs'", text)
        self.assertIn('SELECT COUNT(*) FROM worker_jobs WHERE consumed_at IS NULL', text)
        self.assertIn('drain/classify them before queue isolation migration', text)
        self.assertNotIn('DELETE FROM worker_jobs', text)
        self.assertNotIn('UPDATE worker_jobs SET consumed_at', text)

    def test_systemd_worker_has_private_queue_and_shared_state_is_inaccessible(self):
        text = (SYSTEMD / "factory-cloud-app@.service").read_text(encoding="utf-8")
        self.assertIn("User=factory-cloud-%i", text)
        self.assertIn("Group=factory-cloud-%i", text)
        self.assertNotIn("SupplementaryGroups=", text)
        self.assertIn("UMask=0007", text)
        self.assertIn("factory_cloud.app_worker D", text)
        self.assertIn("--queue /var/lib/factory-cloud/queues/%i/queue.sqlite3", text)
        self.assertIn("--adapter-config /etc/factory-cloud/apps/%i.json", text)
        self.assertIn("ReadWritePaths=/var/lib/factory-cloud/queues/%i", text)
        self.assertIn("InaccessiblePaths=-/var/lib/factory-cloud/state.sqlite3", text)
        self.assertIn("NoNewPrivileges=true", text)

    def test_control_service_uses_queue_directory_not_shared_state_as_job_transport(self):
        text = (SYSTEMD / "factory-cloud-control.service").read_text(encoding="utf-8")
        self.assertIn("factory_cloud.worker D", text)
        self.assertIn("--state /var/lib/factory-cloud/state.sqlite3", text)
        self.assertIn("--queue-dir /var/lib/factory-cloud/queues", text)


if __name__ == "__main__":
    unittest.main()
