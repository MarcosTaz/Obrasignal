from pathlib import Path


CORS_APP = Path("cors_app.py")


def test_canonical_origin_is_code_level_and_wildcard_is_rejected():
    source = CORS_APP.read_text(encoding="utf-8")

    assert 'CANONICAL_WEB_ORIGIN = "https://obrasignal.com"' in source
    assert "for origin in (canonical, configured_primary, configured_fallback, published_fallback)" in source
    assert 'if origin and origin != "*"' in source
    assert 'response.headers["Access-Control-Allow-Origin"] = "*"' not in source


def test_canonical_origin_precedes_lagging_runtime_configuration():
    source = CORS_APP.read_text(encoding="utf-8")

    canonical = source.index("canonical = _normalized_origin(CANONICAL_WEB_ORIGIN)")
    configured = source.index('configured_primary = _normalized_origin(os.getenv("OBRASIGNAL_CORS_ORIGIN") or "")')
    return_order = source.index("for origin in (canonical, configured_primary, configured_fallback, published_fallback)")

    assert canonical < configured < return_order
