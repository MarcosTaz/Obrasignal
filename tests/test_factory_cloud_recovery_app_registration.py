from copy import deepcopy
from pathlib import Path

import pytest

from factory_cloud.control_plane import RegistryError, load_registry, validate_registry
from factory_cloud.process_adapter import ProcessAdapterConfig

EXPECTED_HEAD = "0d1759832a06b3177b67b35a4c53ee0c69db459e"


def test_recovery_apps_are_source_registered_but_runtime_fail_closed():
    registry = load_registry()
    apps = {app["app_id"]: app for app in registry["applications"]}
    for app_id, branch in (
        ("aviation-lease-entitlement-recovery", "apps/aviation-lease-entitlement-recovery"),
        ("contractcredit", "apps/contractcredit"),
    ):
        app = apps[app_id]
        assert app["activation"]["enabled"] is False
        assert app["activation"]["mode"] == "runtime_provisioning_wait"
        assert app["development_state"] == "PILOT_CAPABLE_ASSISTED_RUNTIME_PROVISIONING_WAIT"
        assert app["baton"]["active"] == "runtime:provision"
        assert app["source_truth"]["canonical_branch"] == branch
        assert app["source_truth"]["canonical_head"] == EXPECTED_HEAD
        assert app["execution_source"]["head"] == EXPECTED_HEAD
        assert app["execution_source"]["classification"] == "SOURCE_REGISTERED_APPLICATION_BRANCH_GREEN"
        assert app["execution_adapter"]["repository_mutation_capability"] is False
        assert set(app["execution_adapter"]["allowlisted_tasks"]) == {"verify:service", "verify:shared-contracts"}
        assert any("runtime workspace provisioning" in item for item in app["baton"]["wait"])


def test_disabled_runtime_wait_app_is_still_source_and_capability_validated():
    registry = load_registry()
    broken = deepcopy(registry)
    target = next(app for app in broken["applications"] if app["app_id"] == "contractcredit")
    target["execution_source"]["head"] = "not-a-sha"
    with pytest.raises(RegistryError, match="exact SHA"):
        validate_registry(broken)


def test_runtime_wait_app_cannot_hide_a_stale_active_task():
    registry = load_registry()
    broken = deepcopy(registry)
    target = next(app for app in broken["applications"] if app["app_id"] == "contractcredit")
    target["baton"]["active"] = "verify:service"
    with pytest.raises(RegistryError, match="runtime:provision"):
        validate_registry(broken)


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
