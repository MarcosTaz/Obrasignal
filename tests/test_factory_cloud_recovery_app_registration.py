from pathlib import Path

from factory_cloud.control_plane import load_registry
from factory_cloud.process_adapter import ProcessAdapterConfig

EXPECTED_HEAD = "e8470dbc209c7ec5eaeef7e088573d6adf7cf510"


def test_recovery_apps_are_source_registered_but_runtime_fail_closed():
    registry = load_registry()
    apps = {app["app_id"]: app for app in registry["applications"]}
    for app_id, branch in (
        ("aviation-lease-entitlement-recovery", "apps/aviation-lease-entitlement-recovery"),
        ("contractcredit", "apps/contractcredit"),
    ):
        app = apps[app_id]
        # Source truth is registered, but dispatch must remain disabled until the
        # configured worker workspace/runtime has been provisioned and verified.
        assert app["activation"]["enabled"] is False
        assert app["activation"]["mode"] == "runtime_provisioning_wait"
        assert app["development_state"] == "PILOT_CAPABLE_ASSISTED_RUNTIME_PROVISIONING_WAIT"
        assert app["source_truth"]["canonical_branch"] == branch
        assert app["source_truth"]["canonical_head"] == EXPECTED_HEAD
        assert app["execution_source"]["head"] == EXPECTED_HEAD
        assert app["execution_adapter"]["repository_mutation_capability"] is False
        assert set(app["execution_adapter"]["allowlisted_tasks"]) == {"verify:service", "verify:shared-contracts"}
        assert any("runtime workspace provisioning" in item for item in app["baton"]["wait"])


def test_recovery_runtime_configs_are_process_adapter_valid_but_not_proof_of_provisioning():
    configs = {
        "aviation-lease-entitlement-recovery": Path("factory_cloud/runtime/aviation-recovery-adapter.json"),
        "contractcredit": Path("factory_cloud/runtime/contractcredit-adapter.json"),
    }
    for app_id, path in configs.items():
        config = ProcessAdapterConfig.load(path, expected_app_id=app_id)
        assert config.mode == "repository_safe_execution"
        assert config.command[-1].endswith("recovery_vertical_agent.py")
        assert config.workspace.is_absolute()
