from pathlib import Path


RENDER = Path("render.yaml")
AUTH_E2E = Path(".github/workflows/authenticated-e2e.yml")
CORS = Path("cors_app.py")


def test_current_core_preserves_single_runtime_and_q080_auth_render_contract():
    render = RENDER.read_text(encoding="utf-8")
    assert "cors_app:APP" in render
    assert "OBRASIGNAL_JWT_ISSUER" in render
    assert "OBRASIGNAL_JWKS_URL" not in render
    assert "key: OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1" in render
    assert "key: OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1" in render
    assert render.count('value: "false"') >= 2


def test_current_cumulative_auth_harness_and_security_boundary_coexist():
    workflow = AUTH_E2E.read_text(encoding="utf-8")
    cors = CORS.read_text(encoding="utf-8")

    assert "open('/tmp/authenticated_account_id', 'w', encoding='utf-8').write(str(account_id))" in workflow
    assert "Authenticated API identity verified for account:" not in workflow
    assert "Verify provider READY after authenticated identity" in workflow
    assert "assert auth.get('provider_kind') == 'supabase'" in workflow
    assert "assert auth.get('provider_status') == 'ready'" in workflow
    assert "assert auth.get('provider_error') is None" in workflow
    assert "assert health.get('build') == os.environ['TARGET_BUILD']" in workflow

    assert "import api as _api_module" in cors
    assert "request.obrasignal_identity = identity" in cors
    assert 'response.headers["X-Content-Type-Options"] = "nosniff"' in cors
    assert 'response.headers["X-Frame-Options"] = "DENY"' in cors
    assert "_API_JSON_WRITE_MAX_BYTES" in cors
