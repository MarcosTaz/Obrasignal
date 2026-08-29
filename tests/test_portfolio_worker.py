import json
import subprocess
from pathlib import Path

from factory_cloud.portfolio_worker import (
    PortfolioExecutionRequest,
    PortfolioFactoryWorker,
    configured_endpoint,
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


def test_shared_endpoint_configuration_is_one_global_https_url():
    endpoint = configured_endpoint({"FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT": "https://worker.example.test/v1/execute"})
    assert endpoint == "https://worker.example.test/v1/execute"


def test_remote_http_endpoint_is_rejected_but_localhost_is_allowed():
    worker = PortfolioFactoryWorker(
        environ={"FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT": "http://worker.example.test/v1/execute"}
    )
    result = worker.execute(request())
    assert result["status"] == "BLOCKED"
    assert result["error"]["type"] == "INVALID_WORKER_CONFIGURATION"
    assert configured_endpoint({"FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT": "http://127.0.0.1:8788/execute"})


def test_relative_worker_path_is_rejected():
    worker = PortfolioFactoryWorker(environ={"FACTORY_CLOUD_PORTFOLIO_WORKER": "./worker"})
    result = worker.execute(request())
    assert result["status"] == "BLOCKED"
    assert result["error"]["type"] == "INVALID_WORKER_CONFIGURATION"


def test_executable_and_endpoint_together_are_rejected_as_ambiguous():
    worker = PortfolioFactoryWorker(
        environ={
            "FACTORY_CLOUD_PORTFOLIO_WORKER": "/opt/factory-cloud/portfolio-worker",
            "FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT": "https://worker.example.test/v1/execute",
        }
    )
    result = worker.execute(request())
    assert result["status"] == "BLOCKED"
    assert result["error"]["type"] == "AMBIGUOUS_WORKER_CONFIGURATION"


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


def test_factory_identity_and_baton_are_sent_to_one_shared_endpoint():
    calls = []

    class Response:
        status_code = 200

        def json(self):
            return {"status": "DONE", "evidence": {"worker": "shared-endpoint"}}

    def poster(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    env = {
        "FACTORY_CLOUD_PORTFOLIO_WORKER_ENDPOINT": "https://worker.example.test/v1/execute",
        "FACTORY_CLOUD_PORTFOLIO_WORKER_TOKEN": "secret-token",
    }
    result = PortfolioFactoryWorker(environ=env, poster=poster).execute(request())

    assert result["status"] == "DONE"
    assert result["factory_id"] == "scopeledger"
    assert result["route"] == "factory://portfolio/scopeledger"
    url, kwargs = calls[0]
    assert url == "https://worker.example.test/v1/execute"
    assert kwargs["json"]["factory_id"] == "scopeledger"
    assert kwargs["json"]["baton"]["resume_at"] == "validate"
    assert kwargs["headers"]["authorization"] == "Bearer secret-token"
    assert kwargs["allow_redirects"] is False
