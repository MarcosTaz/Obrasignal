from pathlib import Path

from factory_cloud.global_state_store import GlobalStateStore


def routes():
    return [
        {
            "factory_id": "obrasignal",
            "route": "factory-cloud://apps/obrasignal",
            "worker_key": "app:obrasignal",
        },
        {
            "factory_id": "scopeledger",
            "route": "factory://portfolio/scopeledger",
            "worker_key": "portfolio:scopeledger",
        },
    ]


def test_batch_persists_and_reopens(tmp_path: Path):
    path = tmp_path / "global.sqlite3"
    store = GlobalStateStore(path)
    batch_id = store.create_batch("all", routes())

    reopened = GlobalStateStore(path)
    batch = reopened.batch(batch_id)
    assert batch["state"] == "QUEUED"
    assert len(batch["items"]) == 2
    assert all(item["state"] == "QUEUED" for item in batch["items"])


def test_blocked_factory_does_not_erase_other_factory_progress(tmp_path: Path):
    store = GlobalStateStore(tmp_path / "global.sqlite3")
    batch_id = store.create_batch("all", routes())

    store.update_item(batch_id, "scopeledger", "WAIT", blocker="worker_not_provisioned")
    store.update_item(batch_id, "obrasignal", "DONE", result={"verified": True})

    batch = store.batch(batch_id)
    by_id = {item["factory_id"]: item for item in batch["items"]}
    assert by_id["scopeledger"]["state"] == "WAIT"
    assert by_id["obrasignal"]["state"] == "DONE"
    assert by_id["obrasignal"]["result"] == {"verified": True}
    assert batch["state"] == "PARTIAL"


def test_all_wait_is_blocked_not_false_done(tmp_path: Path):
    store = GlobalStateStore(tmp_path / "global.sqlite3")
    batch_id = store.create_batch("business", routes())
    store.update_item(batch_id, "scopeledger", "WAIT", blocker="external")
    store.update_item(batch_id, "obrasignal", "BLOCKED", blocker="external")
    assert store.batch(batch_id)["state"] == "BLOCKED"


def test_all_done_is_done(tmp_path: Path):
    store = GlobalStateStore(tmp_path / "global.sqlite3")
    batch_id = store.create_batch("all", routes())
    store.update_item(batch_id, "scopeledger", "DONE")
    store.update_item(batch_id, "obrasignal", "DONE")
    assert store.batch(batch_id)["state"] == "DONE"
