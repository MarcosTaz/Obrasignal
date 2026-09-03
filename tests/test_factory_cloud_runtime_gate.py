import pytest

from factory_cloud.control_plane import load_registry
from factory_cloud.runtime_gate import RuntimeGateError, assess_runtime_gate


def test_registered_recovery_apps_remain_ineligible_on_unprovisioned_ci_host():
    apps = {item["app_id"]: item for item in load_registry()["applications"]}
    for app_id in ("aviation-lease-entitlement-recovery", "contractcredit"):
        decision = assess_runtime_gate(apps[app_id])
        assert decision.eligible is False
        assert decision.reason == "runtime_not_provisioned_or_exact_head_unverified"
        assert decision.check.expected_head == apps[app_id]["execution_source"]["head"]


def test_runtime_gate_rejects_non_wait_application():
    apps = {item["app_id"]: item for item in load_registry()["applications"]}
    with pytest.raises(RuntimeGateError, match="only for disabled"):
        assess_runtime_gate(apps["obrasignal"])
