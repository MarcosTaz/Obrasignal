from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_render_keeps_process_isolation_and_measured_io_request_slots():
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "--workers 2" in render
    assert "--worker-class gthread" in render
    assert "--threads 4" in render
    assert "--threads 12" not in render


def test_production_entrypoint_prewarms_auth_before_worker_is_served():
    entrypoint = (ROOT / "production_entrypoint.py").read_text(encoding="utf-8")
    assert "warm_production_auth" in entrypoint
    assert "AUTH_WARM_STATE = warm_production_auth()" in entrypoint


def test_production_entrypoint_forces_preflight_ahead_of_transitive_guards():
    entrypoint = (ROOT / "production_entrypoint.py").read_text(encoding="utf-8")
    assert "_global_hooks.remove(_global_api_preflight)" in entrypoint
    assert "_global_hooks.insert(0, _global_api_preflight)" in entrypoint
