from __future__ import annotations

from pathlib import Path

from factory_cloud.global_runtime import build_global_dispatcher


def test_one_shared_worker_executes_all_business_factories(tmp_path: Path):
    worker = tmp_path / "portfolio-agent"
    worker.write_text(
        "#!/usr/bin/env python3\n"
        "import json,sys\n"
        "request=json.load(sys.stdin)\n"
        "json.dump({'status':'DONE','factory_id':request['factory_id'],'route':request['route'],'evidence':{'worker':'shared'}},sys.stdout)\n",
        encoding="utf-8",
    )
    worker.chmod(0o700)

    dispatcher = build_global_dispatcher(
        environ={"FACTORY_CLOUD_PORTFOLIO_WORKER": str(worker)},
        runtime_dir=tmp_path / "state",
    )
    batch = dispatcher.dispatch("business")

    assert batch["state"] == "DONE"
    assert len(batch["items"]) > 5
    assert all(item["state"] == "DONE" for item in batch["items"])
    assert all(item["result"]["evidence"]["worker"] == "shared" for item in batch["items"])
    assert all(item["result"]["factory_id"] == item["factory_id"] for item in batch["items"])
    assert all("chatgpt.com" not in item["route"] for item in batch["items"])

    persisted = dispatcher.store.batch(batch["batch_id"])
    assert persisted["state"] == "DONE"
    assert {item["factory_id"] for item in persisted["items"]} == {
        item["factory_id"] for item in batch["items"]
    }
