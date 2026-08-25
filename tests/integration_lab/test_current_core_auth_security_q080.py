from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_current_core_keeps_q080_security_and_authoritative_auth_contracts_together():
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "OBRASIGNAL_JWT_ISSUER" in render
    assert "OBRASIGNAL_JWKS_URL" not in render
    assert 'OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1' in render
    assert 'OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1' in render

    authenticated = (ROOT / ".github/workflows/authenticated-e2e.yml").read_text(encoding="utf-8")
    assert "UNKNOWN_NO_DATA" in authenticated
    assert "provider_status" in authenticated
    assert "TARGET_BUILD" in authenticated

    forged = (ROOT / ".github/workflows/auth-forged-signature-e2e.yml").read_text(encoding="utf-8")
    assert "authentication_required" in forged

    cors_app = (ROOT / "cors_app.py").read_text(encoding="utf-8")
    assert "X-Content-Type-Options" in cors_app
    assert "Cache-Control" in cors_app
