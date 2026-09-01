from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_render_keeps_threaded_customer_capacity_beside_ingestion():
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "--workers 2" in render
    assert "--worker-class gthread" in render
    assert "--threads 4" in render
    assert 'key: POLL_SECONDS' in render
    assert 'value: "300"' in render
