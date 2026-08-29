from __future__ import annotations

from pathlib import Path

from factory_cloud.global_runtime import build_global_dispatcher


def test_global_runtime_requires_no_per_factory_paths(tmp_path: Path):
    dispatcher = build_global_dispatcher(environ={}, runtime_dir=tmp_path)
    batch = dispatcher.dispatch("business")
    assert batch["items"]
    assert all(item["state"] == "WAIT" for item in batch["items"])
    assert all(item["blocker"] == "portfolio_factory_worker_not_provisioned" for item in batch["items"])


def test_global_runtime_rejects_relative_shared_state_override(tmp_path: Path):
    try:
        build_global_dispatcher(
            environ={"FACTORY_CLOUD_GLOBAL_STATE": "relative.sqlite3"},
            runtime_dir=tmp_path,
        )
    except ValueError as exc:
        assert "FACTORY_CLOUD_GLOBAL_STATE" in str(exc)
    else:
        raise AssertionError("relative shared state path must be rejected")


def test_global_runtime_rejects_relative_private_queue_override(tmp_path: Path):
    try:
        build_global_dispatcher(
            environ={"FACTORY_CLOUD_QUEUE_DIR": "relative-queues"},
            runtime_dir=tmp_path,
        )
    except ValueError as exc:
        assert "FACTORY_CLOUD_QUEUE_DIR" in str(exc)
    else:
        raise AssertionError("relative private queue path must be rejected")
