from pathlib import Path


def test_render_start_command_pins_exact_company_browser_origins():
    render = Path("render.yaml").read_text(encoding="utf-8")
    start = next(line.strip() for line in render.splitlines() if line.strip().startswith("startCommand:"))

    assert "OBRASIGNAL_CORS_ORIGIN=https://obrasignal.com" in start
    assert "OBRASIGNAL_CORS_FALLBACK_ORIGIN=https://marcostaz.github.io" in start
    assert "OBRASIGNAL_CORS_ORIGIN=*" not in start
    assert "OBRASIGNAL_CORS_FALLBACK_ORIGIN=*" not in start
    assert "--workers 2" in start
    assert "--threads 4" in start
