from runtime_deferred_worker import (
    DEFAULT_SOURCE_START_DELAY_SECONDS,
    MAX_SOURCE_START_DELAY_SECONDS,
    source_start_delay_seconds,
    start_source_worker_after_readiness,
)


class ImmediateThread:
    def __init__(self, *, target, args, name, daemon):
        self.target = target
        self.args = args
        self.name = name
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True
        self.target(*self.args)


def test_default_delay_protects_http_readiness(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_SOURCE_START_DELAY_SECONDS", raising=False)
    assert source_start_delay_seconds() == DEFAULT_SOURCE_START_DELAY_SECONDS
    assert DEFAULT_SOURCE_START_DELAY_SECONDS >= 60


def test_env_delay_is_bounded(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_SOURCE_START_DELAY_SECONDS", "9999")
    assert source_start_delay_seconds() == MAX_SOURCE_START_DELAY_SECONDS
    monkeypatch.setenv("OBRASIGNAL_SOURCE_START_DELAY_SECONDS", "invalid")
    assert source_start_delay_seconds() == DEFAULT_SOURCE_START_DELAY_SECONDS


def test_source_worker_starts_only_after_grace():
    events = []

    def sleep(seconds):
        events.append(("sleep", seconds))

    def worker():
        events.append(("worker", None))

    thread = start_source_worker_after_readiness(
        worker,
        delay_seconds=75,
        sleep_func=sleep,
        thread_factory=ImmediateThread,
    )

    assert thread.started is True
    assert thread.daemon is True
    assert events == [("sleep", 75), ("worker", None)]
