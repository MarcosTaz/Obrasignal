from pathlib import Path

from source_registry import SOURCES


def test_france_decp_uses_single_canonical_wsgi_composition_root():
    render = Path("render.yaml").read_text(encoding="utf-8")
    cors = Path("cors_app.py").read_text(encoding="utf-8")

    assert "cors_app:APP" in render
    assert "france_app:APP" not in render
    assert not Path("france_app.py").exists()
    assert "from france_runtime import install_france_decp_runtime" in cors
    assert "install_france_decp_runtime(" in cors


def test_france_decp_registry_does_not_activate_or_promote_wave():
    source = SOURCES["FR_DECP"]

    assert source["status"] == "ready"
    assert source["wave"] is None
    assert source["signal_types"] == ("CONTRACT",)
    assert source["legal_reuse"] == "GREEN"
    assert source["machine_access"] == "VERIFIED"
