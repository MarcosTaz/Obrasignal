import json
import subprocess
from pathlib import Path

from factory_cloud.portfolio_worker import (
    PortfolioExecutionRequest,
    PortfolioFactoryWorker,
    configured_executor,
)


def request():
    return PortfolioExecutionRequest(
        factory_id="scopeledger",
        route="factory://portfolio/scopeledger",
        signal="X",
        mission="resume",
        baton={"active": "validate", "resume_at": "validate"},
    )


def test_missing_global_worker_fails_closed_without_manual_factory_path():
    worker = PortfolioFactoryWorker(environ={})
    result = worker.execute(request())
    assert result["status"] == "WAIT"
    assert result["blockers"] == ["portfolio_factory_worker_not_provisioned"]
    assert result["resume_at"] == "validate"


def test_executor_configuration_is_one_global_absolute_path():
    path = configured_executor({"FACTORY_CLOUD_PORTFOLIO_WORKER": "/opt/factory-cloud/portfolio-worker"})
    assert path == Path("/opt/factory-cloud/portfolio-worker")


def test_relative_worker_path_is_rejected():
    worker = PortfolioFactoryWorker(environ={"FACTORY_CLOUD_PORTFOLIO_WORKER": "./worker"})
    result = worker.execute(request())
    assert result["status"] == "BLOCKED"
    assert result["error"]["type"] == "INVALID_WORKER_CONFIGURATION"


def test_factory_identity_and_baton_are_sent_over_stdin_not_shell_arguments():
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"status": "DONE"}), stderr="")

    env = {"FACTORY_CLOUD_PORTFOLIO_WORKER": "/opt/factory-cloud/portfolio-worker"}
    result = PortfolioFactoryWorker(environ=env, runner=runner).execute(request())

    assert result["status"] == "DONE"
    argv, kwargs = calls[0]
    assert argv == ["/opt/factory-cloud/portfolio-worker"]
    sent = json.loads(kwargs["input"])
    assert sent["factory_id"] == "scopeledger"
    assert sent["route"] == "factory://portfolio/scopeledger"
    assert sent["baton"]["resume_at"] == "validate"
    assert kwargs["check"] is False
    assert kwargs["capture_output"] is True
