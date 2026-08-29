import json

import pytest

from factory_cloud.runtime_provisioning import RuntimeProvisioningError, inspect_runtime, require_runtime


def _config(path, *, app_id, workspace, command):
    path.write_text(json.dumps({
        "app_id": app_id,
        "mode": "repository_safe_execution",
        "workspace": str(workspace),
        "command": ["/usr/bin/python3", str(command)],
        "capabilities": ["READ_REPOSITORY", "RUN_TESTS", "UPDATE_BATON"],
        "timeout_seconds": 60,
    }), encoding="utf-8")


def test_runtime_is_not_ready_when_workspace_or_agent_is_missing(tmp_path):
    config = tmp_path / "adapter.json"
    workspace = tmp_path / "missing-workspace"
    agent = tmp_path / "missing-agent.py"
    _config(config, app_id="x", workspace=workspace, command=agent)
    check = inspect_runtime(config, expected_app_id="x")
    assert check.ready is False
    assert check.workspace_exists is False
    assert check.command_exists is False
    with pytest.raises(RuntimeProvisioningError, match="runtime not provisioned"):
        require_runtime(config, expected_app_id="x")


def test_runtime_becomes_ready_only_when_both_paths_exist(tmp_path):
    config = tmp_path / "adapter.json"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = tmp_path / "agent.py"
    agent.write_text("print('ok')\n", encoding="utf-8")
    _config(config, app_id="x", workspace=workspace, command=agent)
    check = require_runtime(config, expected_app_id="x")
    assert check.ready is True
    assert check.workspace == workspace
    assert check.command_path == agent
