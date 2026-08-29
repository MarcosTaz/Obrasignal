from pathlib import Path

from factory_cloud.control_plane import load_registry
from factory_cloud.process_adapter import ProcessAdapterConfig

CANONICAL_HEAD = "5b26801d5d54f224f1da36bb66ba8d26f1f8208c"
CANDIDATE_HEAD = "5657c8c17c2cd1af09d0934299afbe91aed6438b"


def test_recovery_apps_preserve_canonical_authority_and_verify_separate_candidate():
    registry = load_registry()
    apps = {app["app_id"]: app for app in registry["applications"]}
    expected = {
        "aviation-lease-entitlement-recovery": (
            "apps/aviation-lease-entitlement-recovery",
            "apps/aviation-lease-entitlement-recovery-pilot-safe-candidate-20260829",
        ),
        "contractcredit": (
            "apps/contractcredit",
            "apps/contractcredit-pilot-safe-candidate-20260829",
        ),
    }
    for app_id, (canonical_branch, candidate_branch) in expected.items():
        app = apps[app_id]
        assert app["activation"]["enabled"] is True
        assert app["activation"]["mode"] == "repository_safe_execution"
        assert app["source_truth"]["canonical_branch"] == canonical_branch
        assert app["source_truth"]["canonical_head"] == CANONICAL_HEAD
        assert app["execution_source"]["branch"] == candidate_branch
        assert app["execution_source"]["head"] == CANDIDATE_HEAD
        assert app["execution_source"]["verified"] is True
        assert app["execution_source"]["classification"] == "NONCANONICAL_PILOT_SAFE_CANDIDATE_GREEN"
        assert app["execution_adapter"]["repository_mutation_capability"] is False
        assert set(app["execution_adapter"]["allowlisted_tasks"]) == {"verify:service", "verify:shared-contracts"}


def test_recovery_runtime_configs_are_process_adapter_valid():
    configs = {
        "aviation-lease-entitlement-recovery": Path("factory_cloud/runtime/aviation-recovery-adapter.json"),
        "contractcredit": Path("factory_cloud/runtime/contractcredit-adapter.json"),
    }
    for app_id, path in configs.items():
        config = ProcessAdapterConfig.load(path, expected_app_id=app_id)
        assert config.mode == "repository_safe_execution"
        assert config.command[-1].endswith("recovery_vertical_agent.py")
        assert config.workspace.is_absolute()
