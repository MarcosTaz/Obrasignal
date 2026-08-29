from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

from factory_cloud.global_app_executor import FactoryCloudRouteExecutor
from factory_cloud.global_runtime import build_global_dispatcher
from factory_cloud.state_store import utc_now
from factory_cloud.verification import GitHubHeadVerifier, SourceVerification
from factory_cloud.work_queue import app_queue_path


def _verified(repository: str, branch: str, expected_head: str | None) -> SourceVerification:
    return SourceVerification(
        status="VERIFIED",
        verified_at=utc_now(),
        expected_head=expected_head,
        observed_head=expected_head,
        evidence={"repository": repository, "branch": branch, "head": expected_head},
    )


def _has_worker_jobs(path: Path) -> bool:
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='worker_jobs'"
        ).fetchone() is not None


def test_direct_global_app_route_creates_job_only_in_private_obrasignal_queue(tmp_path: Path):
    state_path = tmp_path / "state.sqlite3"
    queue_dir = tmp_path / "queues"
    bridge = FactoryCloudRouteExecutor(state_path, queue_dir=queue_dir)

    with patch.object(GitHubHeadVerifier, "verify", side_effect=_verified):
        result = bridge.execute_app(
            {"factory_id": "obrasignal", "route": "factory-cloud://apps/obrasignal"}
        )

    assert result["status"] == "WAIT"
    assert "app_worker_execution_pending" in result["blockers"]
    assert state_path.is_file()
    assert _has_worker_jobs(state_path) is False

    obra_queue = app_queue_path(queue_dir, "obrasignal")
    assert obra_queue.is_file()
    assert _has_worker_jobs(obra_queue) is True
    with sqlite3.connect(obra_queue) as conn:
        rows = conn.execute("SELECT app_id, status FROM worker_jobs").fetchall()
    assert rows == [("obrasignal", "QUEUED")]
    assert not app_queue_path(queue_dir, "k3-fatality").exists()


def test_D_development_dispatch_reuses_same_private_pending_job(tmp_path: Path):
    dispatcher = build_global_dispatcher(environ={}, runtime_dir=tmp_path)

    with patch.object(GitHubHeadVerifier, "verify", side_effect=_verified):
        batch = dispatcher.dispatch("development")

    by_id = {item["factory_id"]: item for item in batch["items"]}
    assert set(by_id) == {"factory-cloud", "obrasignal"}
    assert by_id["factory-cloud"]["state"] == "WAIT"
    assert by_id["obrasignal"]["state"] == "WAIT"

    app_state = tmp_path / "state.sqlite3"
    assert _has_worker_jobs(app_state) is False
    obra_queue = app_queue_path(tmp_path / "queues", "obrasignal")
    with sqlite3.connect(obra_queue) as conn:
        rows = conn.execute("SELECT app_id, task, status FROM worker_jobs").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "obrasignal"
    assert rows[0][2] == "QUEUED"
    assert not app_queue_path(tmp_path / "queues", "k3-fatality").exists()
