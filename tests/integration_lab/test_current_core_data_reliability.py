from pathlib import Path


CORS = Path("cors_app.py")
PRELOAD = Path("preload.py")
RENDER = Path("render.yaml")


def test_storage_serialization_is_semantically_unioned_with_current_security_boundary():
    cors = CORS.read_text(encoding="utf-8")
    assert "from storage_migration_lock import run_serialized_schema_init" in cors
    assert "run_serialized_schema_init(_initialize_persistent_schema, _app.DB)" in cors
    assert "def _initialize_persistent_schema():" in cors
    assert "import api as _api_module" in cors
    assert "request.obrasignal_identity = identity" in cors
    assert "_API_JSON_WRITE_MAX_BYTES" in cors
    assert 'response.headers["X-Content-Type-Options"] = "nosniff"' in cors
    assert 'response.headers["X-Frame-Options"] = "DENY"' in cors


def test_current_ted_checkpoint_is_staged_until_canonical_persistence_commit():
    preload = PRELOAD.read_text(encoding="utf-8")
    assert 'stage_source_sync("TED", normalized, watermark)' in preload
    assert "record = _app.normalize_ted(row)" in preload
    assert "set_source_cursor" not in preload
    assert "commit_staged_source_syncs" in preload
    assert "discard_staged_source_syncs" in preload


def test_data_reliability_overlay_does_not_change_q080_auth_rollout_contract():
    render = RENDER.read_text(encoding="utf-8")
    assert "OBRASIGNAL_JWT_ISSUER" in render
    assert "OBRASIGNAL_JWKS_URL" not in render
    assert "key: OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1" in render
    assert "key: OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1" in render
