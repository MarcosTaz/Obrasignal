import sqlite3

import pytest

import app
import preload
from source_health import source_health_snapshot


def _connect(path):
    def connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    return connect


def test_unexpected_empty_ted_result_is_a_visible_failure(monkeypatch, tmp_path):
    connect = _connect(tmp_path / "health.db")
    monkeypatch.setattr(preload._app, "db", connect)
    monkeypatch.setattr(preload, "_fetch_ted_resilient", lambda: [])

    with pytest.raises(RuntimeError, match="unexpected empty"):
        preload._fetch_ted_with_health()

    row = source_health_snapshot(connect())[0]
    assert row["source"] == "TED"
    assert row["status"] == "degraded"
    assert "unexpected empty" in row["last_error"]


def test_national_source_failures_are_isolated_and_recorded(monkeypatch, tmp_path):
    connect = _connect(tmp_path / "national-health.db")
    monkeypatch.setattr(preload._app, "db", connect)
    monkeypatch.delenv("BASE_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(preload._national_sources, "fetch_boamp", lambda: [{
        "source": "BOAMP", "external_id": "B-1", "title": "Travaux"
    }])
    monkeypatch.setattr(preload._national_sources, "fetch_placsp", lambda: (_ for _ in ()).throw(RuntimeError("HTTP 429")))
    monkeypatch.setattr(preload._national_sources, "LUXEMBOURG_RSS_URL", "")

    rows = preload.fetch_base_with_national_sources()
    health = {row["source"]: row for row in source_health_snapshot(connect())}

    assert [(row["source"], row["external_id"]) for row in rows] == [("BOAMP", "B-1")]
    assert health["BOAMP"]["status"] == "healthy"
    assert health["PLACSP"]["status"] == "degraded"
    assert "HTTP 429" in health["PLACSP"]["last_error"]
    assert health["BASE"]["status"] == "degraded"
    assert "not configured" in health["BASE"]["last_error"]


def test_source_failure_does_not_delete_previously_ingested_opportunities(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DB", str(tmp_path / "preserve.db"))
    app.init_db()
    conn = app.db()
    conn.execute("INSERT INTO tenders(source,external_id,title,first_seen,last_seen) VALUES('TED','KEEP-1','Existing','2026-01-01','2026-01-01')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(app, "fetch_ted", lambda: (_ for _ in ()).throw(RuntimeError("HTTP 500")))

    with pytest.raises(RuntimeError, match="HTTP 500"):
        app.sync_once()

    conn = app.db()
    assert conn.execute("SELECT COUNT(*) FROM tenders WHERE external_id='KEEP-1'").fetchone()[0] == 1
    conn.close()


def test_render_uses_one_persistent_sqlite_store_with_spare_http_worker():
    manifest = open("render.yaml", encoding="utf-8").read()
    entrypoint = open("cors_app.py", encoding="utf-8").read()
    assert manifest.count("- type: web") == 1
    assert 'mountPath: /var/data' in manifest
    assert 'OBRASIGNAL_DB' in manifest
    assert 'value: "/var/data/obrasignal.db"' in manifest
    assert '--workers 2' in manifest
    assert 'if acquire_runtime_leader():' in entrypoint
    leader_block = entrypoint.split('if acquire_runtime_leader():', 1)[1]
    assert 'start_background_worker()' in leader_block
    assert 'start_push_scheduler()' in leader_block
