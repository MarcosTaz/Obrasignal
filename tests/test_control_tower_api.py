from __future__ import annotations

from pathlib import Path

from factory_cloud.control_tower_api import handle_request
from factory_cloud.global_dispatcher import GlobalDispatcher
from factory_cloud.portfolio_worker import PortfolioExecutionRequest


class DonePortfolioWorker:
    def execute(self, request: PortfolioExecutionRequest):
        return {"status": "DONE", "evidence": {"factory_id": request.factory_id}, "blockers": []}


def _done(request):
    return {"status": "DONE", "evidence": {"route": request["route"]}, "blockers": []}


def test_one_api_order_dispatches_obrasignal_hierarchy(tmp_path: Path):
    dispatcher = GlobalDispatcher(
        tmp_path / "tower.sqlite3",
        control_executor=_done,
        app_executor=_done,
        portfolio_worker=DonePortfolioWorker(),
    )

    status, payload = handle_request(
        dispatcher,
        method="POST",
        path="/v1/dispatch",
        body={"scope": "obrasignal"},
    )

    assert status == 202
    ids = {item["factory_id"] for item in payload["items"]}
    assert "obrasignal" in ids
    assert "obrasignal-customer-journey" in ids
    assert "industrial-claims" not in ids
    assert payload["state"] == "DONE"


def test_batch_can_be_read_without_factory_paths(tmp_path: Path):
    dispatcher = GlobalDispatcher(
        tmp_path / "tower.sqlite3",
        control_executor=_done,
        app_executor=_done,
        portfolio_worker=DonePortfolioWorker(),
    )
    _, created = handle_request(
        dispatcher,
        method="POST",
        path="/v1/dispatch",
        body={"scope": "business"},
    )

    status, loaded = handle_request(
        dispatcher,
        method="GET",
        path=f"/v1/batches/{created['batch_id']}",
    )

    assert status == 200
    assert loaded["batch_id"] == created["batch_id"]
    assert all("chat" not in item["route"] for item in loaded["items"])


def test_unknown_scope_is_rejected(tmp_path: Path):
    dispatcher = GlobalDispatcher(tmp_path / "tower.sqlite3", portfolio_worker=DonePortfolioWorker())
    status, payload = handle_request(
        dispatcher,
        method="POST",
        path="/v1/dispatch",
        body={"scope": "missing-factory"},
    )
    assert status == 400
    assert payload["error"] == "dispatch_rejected"
