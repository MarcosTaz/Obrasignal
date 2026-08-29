from factory_cloud.adapters import AdapterRegistry, ExecutionRequest, ExecutionResult
from factory_cloud.app_worker import AppWorkerHost
from factory_cloud.state_store import StateStore
from factory_cloud.work_queue import DurableWorkQueue


class DoneAdapter:
    def execute(self, request):
        return ExecutionResult(
            status="DONE",
            evidence={"task_state": "VERIFIED"},
            next_active="",
            resume_at="",
        )


def _seed(store, app_id):
    store.upsert_from_registry({
        "app_id": app_id,
        "mission": "test",
        "source_truth": {"provider": "github", "repository": "MarcosTaz/Obrasignal", "canonical_head": "a" * 40, "verified": True},
        "activation": {"priority": 1},
        "baton": {"active": "verify:service", "next": [], "wait": []},
        "development_state": "READY",
    })


def _request(app_id):
    return ExecutionRequest(
        app_id=app_id,
        mode="repository_safe_execution",
        task="verify:service",
        source="MarcosTaz/Obrasignal",
        canonical_head="a" * 40,
        execution_branch="apps/test",
        execution_head="a" * 40,
        required_capabilities=(),
        resume_at="verify:service",
    )


def test_two_recovery_workers_are_app_isolated_and_durable(tmp_path):
    store = StateStore(tmp_path / "state.sqlite3")
    queue = DurableWorkQueue(store)
    apps = ("aviation-lease-entitlement-recovery", "contractcredit")
    for app_id in apps:
        _seed(store, app_id)
        queue.submit_or_get(_request(app_id))

    adapters = AdapterRegistry({app_id: DoneAdapter() for app_id in apps})
    aviation_worker = AppWorkerHost(apps[0], queue, adapters=adapters, worker_id="aviation-worker", job_lease_seconds=10)
    credit_worker = AppWorkerHost(apps[1], queue, adapters=adapters, worker_id="credit-worker", job_lease_seconds=10)

    aviation = aviation_worker.run_once()
    credit = credit_worker.run_once()
    assert aviation["state"] == "DONE"
    assert credit["state"] == "DONE"
    assert queue.jobs(apps[0])[0]["claimed_by"] == "aviation-worker"
    assert queue.jobs(apps[1])[0]["claimed_by"] == "credit-worker"
