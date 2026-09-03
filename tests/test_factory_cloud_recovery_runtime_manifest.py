import json
from pathlib import Path

from factory_cloud.control_plane import load_registry
from factory_cloud.process_adapter import ProcessAdapterConfig

MANIFEST = Path("factory_cloud/runtime/recovery-runtime-provisioning.json")


def test_recovery_runtime_manifest_matches_registry_and_adapter_contracts():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["supervision_required"] is True
    apps = {item["app_id"]: item for item in load_registry()["applications"]}
    for item in manifest["applications"]:
        app = apps[item["app_id"]]
        execution = app["execution_source"]
        assert item["repository"] == execution["repository"]
        assert item["branch"] == execution["branch"]
        assert item["head"] == execution["head"]
        config = ProcessAdapterConfig.load(Path(item["adapter_config"]), expected_app_id=item["app_id"])
        assert item["workspace"] == str(config.workspace)
        assert item["agent"] == config.command[-1]
        assert set(item["activation_after"]) == {
            "workspace_exists",
            "exact_head_matches",
            "agent_exists",
            "verification_tests_pass",
            "supervised_worker_confirmed",
        }
