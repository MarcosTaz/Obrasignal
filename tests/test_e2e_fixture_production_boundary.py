from pathlib import Path


def test_production_wsgi_does_not_register_test_fixture_api():
    """Synthetic fixture routes must be impossible on the production entrypoint."""
    render = Path("render.yaml").read_text(encoding="utf-8")
    cors_source = Path("cors_app.py").read_text(encoding="utf-8")

    assert "cors_app:APP" in render
    assert "install_e2e_fixture_api(APP)" not in cors_source
    assert "from e2e_fixture_api import install as install_e2e_fixture_api" not in cors_source
