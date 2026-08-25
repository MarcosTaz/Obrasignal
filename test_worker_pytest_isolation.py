import app


def test_pytest_process_does_not_start_background_ingestion_worker():
    # conftest.py establishes this before test-module collection. Keeping this
    # assertion explicit prevents a future test harness change from silently
    # reintroducing concurrent network ingestion into deterministic CI.
    assert app._worker_started is True
