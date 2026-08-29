from __future__ import annotations

from pathlib import Path

from factory_cloud.global_dispatcher import GlobalDispatcher
from factory_cloud.portfolio_worker import PortfolioExecutionRequest


class FakePortfolioWorker:
    def execute(self, request: PortfolioExecutionRequest):
        if request.factory_id == "industrial-claims":
            return {
                "status": "BLOCKED",
                "blockers": ["synthetic_local_blocker"],
                "resume_at": request.baton.get("resume_at"),
            }
        return {
            "status": "DONE",
            "evidence": {"synthetic": True},
            "blockers": [],
        }


def _done(request):
    return {"status": "DONE", "evidence": {"route": request["route"]}, "blockers": []}


def test_global_dispatch_continues_after_blocked_factory(tmp_path: Path):
    dispatcher = GlobalDispatcher(
        tmp_path / "tower.sqlite3",
        control_executor=_done,
        app_executor=_done,
        portfolio_worker=FakePortfolioWorker(),
    )

    batch = dispatcher.dispatch("all")
    states = {item["factory_id"]: item["state"] for item in batch["items"]}

    assert states["industrial-claims"] == "BLOCKED"
    assert states["scopeledger"] == "DONE"
    assert states["obrasignal"] == "DONE"
    assert states["factory-cloud"] == "DONE"
    assert batch["state"] == "PARTIAL"


def test_obrasignal_scope_includes_parent_and_subs_only(tmp_path: Path):
    dispatcher = GlobalDispatcher(
        tmp_path / "tower.sqlite3",
        control_executor=_done,
        app_executor=_done,
        portfolio_worker=FakePortfolioWorker(),
    )

    batch = dispatcher.dispatch("obrasignal")
    ids = {item["factory_id"] for item in batch["items"]}

    assert "obrasignal" in ids
    assert "obrasignal-data-runner" in ids
    assert "industrial-claims" not in ids
    assert "factory-cloud" not in ids


def test_unwired_executors_fail_closed_not_running(tmp_path: Path):
    dispatcher = GlobalDispatcher(tmp_path / "tower.sqlite3", portfolio_worker=FakePortfolioWorker())
    batch = dispatcher.dispatch("development")
    states = {item["factory_id"]: item for item in batch["items"]}

    assert states["factory-cloud"]["state"] == "WAIT"
    assert states["obrasignal"]["state"] == "WAIT"
    assert batch["state"] == "BLOCKED"
