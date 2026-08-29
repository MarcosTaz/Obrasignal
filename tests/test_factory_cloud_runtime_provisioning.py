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
    check = inspect_runtime(config, expected_app_id="x", expected_head="a" * 40)
    assert check.ready is False
    assert check.workspace_exists is False
    assert check.command_exists is False
    with pytest.raises(RuntimeProvisioningError, match="runtime not provisioned"):
        require_runtime(config, expected_app_id="x", expected_head="a" * 40)


def test_runtime_rejects_existing_workspace_on_wrong_head(tmp_path):
    config = tmp_path / "adapter.json"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = tmp_path / "agent.py"
    agent.write_text("print('ok')\n", encoding="utf-8")
    _config(config, app_id="x", workspace=workspace, command=agent)
    check = inspect_runtime(
        config,
        expected_app_id="x",
        expected_head="a" * 40,
        head_reader=lambda _: "b" * 40,
    )
    assert check.workspace_exists is True
    assert check.command_exists is True
    assert check.head_matches is False
    assert check.ready is False
    with pytest.raises(RuntimeProvisioningError, match="head:expected"):
        require_runtime(
            config,
            expected_app_id="x",
            expected_head="a" * 40,
            head_reader=lambda _: "b" * 40,
        )


def test_runtime_becomes_ready_only_with_paths_and_exact_head(tmp_path):
    config = tmp_path / "adapter.json"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = tmp_path / "agent.py"
    agent.write_text("print('ok')\n", encoding="utf-8")
    _config(config, app_id="x", workspace=workspace, command=agent)
    expected = "a" * 40
    check = require_runtime(
        config,
        expected_app_id="x",
        expected_head=expected,
        head_reader=lambda _: expected,
    )
    assert check.ready is True
    assert check.workspace == workspace
    assert check.command_path == agent
    assert check.observed_head == expected
