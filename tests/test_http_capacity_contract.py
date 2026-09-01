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


def test_authoritative_cors_wsgi_module_also_prewarms_auth():
    source = (ROOT / "cors_app.py").read_text(encoding="utf-8")
    # Production evidence showed the live service can import cors_app directly;
    # auth warming therefore cannot exist only in an optional wrapper module.
    assert "from runtime_auth_warm import warm_production_auth" in source
    warm_at = source.rindex("AUTH_WARM_STATE = warm_production_auth()")
    leader_at = source.index("if acquire_runtime_leader():")
    assert warm_at > leader_at


def test_authoritative_cors_wsgi_module_makes_preflight_first_itself():
    source = (ROOT / "cors_app.py").read_text(encoding="utf-8")
    handler_at = source.index("def _global_api_preflight():")
    remove_at = source.index("_global_hooks.remove(_global_api_preflight)", handler_at)
    first_at = source.index("_global_hooks.insert(0, _global_api_preflight)", remove_at)
    deletion_guard_at = source.index("def _lock_private_shell_during_account_deletion():")
    assert handler_at < remove_at < first_at < deletion_guard_at


def test_health_exposes_bounded_runtime_readiness_not_secrets():
    source = (ROOT / "cors_app.py").read_text(encoding="utf-8")
    assert '"auth_warm_status"' in source
    assert '"preflight_first"' in source
    assert "jwks_url" not in source
    assert "JWT_ISSUER" not in source
