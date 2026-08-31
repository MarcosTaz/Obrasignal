import json
from copy import deepcopy
from pathlib import Path

import pytest

from factory_cloud.control_plane import RegistryError, load_registry, validate_registry
from factory_cloud.process_adapter import ProcessAdapterConfig


PROVISIONING_PATH = Path("factory_cloud/runtime/recovery-runtime-provisioning.json")


def _provisioning_by_app() -> dict[str, dict]:
    document = json.loads(PROVISIONING_PATH.read_text(encoding="utf-8"))
    return {item["app_id"]: item for item in document["applications"]}


def test_recovery_apps_are_source_registered_but_runtime_fail_closed():
    registry = load_registry()
    apps = {app["app_id"]: app for app in registry["applications"]}
    provisioning = _provisioning_by_app()
    expected = (
        (
            "aviation-lease-entitlement-recovery",
            "apps/aviation-lease-entitlement-recovery",
            "PILOT_CAPABLE_ASSISTED_RUNTIME_PROVISIONING_WAIT",
            "runtime_provisioning_wait",
            "runtime:provision",
        ),
        (
            "contractcredit",
            "apps/contractcredit",
            "PILOT_CAPABLE_ASSISTED_RUNTIME_PROVISIONING_WAIT",
            "runtime_provisioning_wait",
            "runtime:provision",
        ),
        (
            "industrial-claims",
            "apps/industrial-claims",
            "ASSISTED_RUNTIME_PROVISIONING_WAIT",
            "assisted_business_runtime_wait",
            "business:real-case",
        ),
    )
    for app_id, branch, development_state, activation_mode, active_task in expected:
        app = apps[app_id]
        provisioned = provisioning[app_id]
        expected_head = provisioned["head"]
        assert app["activation"]["enabled"] is False
        assert app["activation"]["mode"] == activation_mode
        assert app["development_state"] == development_state
        assert app["baton"]["active"] == active_task
        assert app["source_truth"]["canonical_branch"] == branch
        assert provisioned["branch"] == branch
        assert app["source_truth"]["canonical_head"] == expected_head
        assert app["execution_source"]["head"] == expected_head
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


def test_assisted_business_runtime_wait_cannot_hide_a_stale_active_task():
    registry = load_registry()
    broken = deepcopy(registry)
    target = next(app for app in broken["applications"] if app["app_id"] == "industrial-claims")
    target["baton"]["active"] = "verify:service"
    with pytest.raises(RegistryError, match="business:real-case"):
        validate_registry(broken)


def test_assisted_business_runtime_wait_cannot_drop_runtime_provisioning_gate():
    registry = load_registry()
    broken = deepcopy(registry)
    target = next(app for app in broken["applications"] if app["app_id"] == "industrial-claims")
    target["baton"]["wait"] = [
        item for item in target["baton"]["wait"] if "runtime workspace provisioning" not in item
    ]
    with pytest.raises(RegistryError, match="runtime provisioning gate"):
        validate_registry(broken)


def test_recovery_runtime_configs_are_process_adapter_valid_but_not_proof_of_provisioning():
    configs = {
        "aviation-lease-entitlement-recovery": Path("factory_cloud/runtime/aviation-recovery-adapter.json"),
        "contractcredit": Path("factory_cloud/runtime/contractcredit-adapter.json"),
        "industrial-claims": Path("factory_cloud/runtime/industrial-claims-adapter.json"),
    }
    for app_id, path in configs.items():
        config = ProcessAdapterConfig.load(path, expected_app_id=app_id)
        assert config.mode == "repository_safe_execution"
        assert config.command[-1].endswith("recovery_vertical_agent.py")
        assert config.workspace.is_absolute()
