from __future__ import annotations

from pathlib import Path

from factory_cloud.adapters import AdapterRegistry, ExecutionResult
from factory_cloud.global_app_executor import FactoryCloudRouteExecutor


class DoneAdapter:
    def execute(self, request):
        return ExecutionResult(
            status="DONE",
            evidence={"task": request.task},
            blockers=(),
            resume_at=request.task,
            last_verified=request.target_head,
            last_green=request.target_head,
        )


def test_obrasignal_global_route_executes_through_durable_orchestrator(tmp_path: Path):
    bridge = FactoryCloudRouteExecutor(
        tmp_path / "app-state.sqlite3",
        adapters=AdapterRegistry({"obrasignal": DoneAdapter()}),
    )
    result = bridge.execute_app({"factory_id": "obrasignal", "route": "factory-cloud://apps/obrasignal"})
    assert result["status"] == "DONE"
    assert result["factory_id"] == "obrasignal"
    persisted = bridge.orchestrator.store.get_app("obrasignal")
    assert persisted is not None
    assert persisted["state"] == "READY"


def test_unknown_app_route_fails_closed(tmp_path: Path):
    bridge = FactoryCloudRouteExecutor(tmp_path / "app-state.sqlite3")
    result = bridge.execute_app({"factory_id": "missing", "route": "factory-cloud://apps/missing"})
    assert result["status"] == "BLOCKED"
    assert result["blockers"] == ["app_not_registered_in_factory_cloud"]
