from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_render_keeps_process_isolation_and_24_io_request_slots():
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "--workers 2" in render
    assert "--worker-class gthread" in render
    assert "--threads 12" in render


def test_production_entrypoint_prewarms_auth_before_worker_is_served():
    entrypoint = (ROOT / "production_entrypoint.py").read_text(encoding="utf-8")
    assert "warm_production_auth" in entrypoint
    assert "AUTH_WARM_STATE = warm_production_auth()" in entrypoint
