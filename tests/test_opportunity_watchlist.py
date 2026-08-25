import sqlite3

import pytest

import app
import account_registry
import opportunity_watchlist_api  # registers the isolated blueprint on api.APP
from api import APP
from opportunity_workflow import (
    NOTE_MAX_LENGTH,
    ensure_workflow_table,
    get_saved_opportunity,
    get_workflow,
    list_saved_opportunities,
    save_opportunity,
    unsave_opportunity,
    update_saved_opportunity,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            title TEXT,
            buyer TEXT,
            country TEXT,
            deadline TEXT,
            url TEXT,
            score INTEGER DEFAULT 0,
            market TEXT,
            first_seen TEXT,
            last_seen TEXT,
            UNIQUE(source, external_id)
        )"""
    )
    conn.executemany(
        """INSERT INTO tenders(source, external_id, title, buyer, country, deadline, url, score, market, first_seen, last_seen)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        [
            ("TED", "A-1", "Aberta", "Buyer A", "PRT", "2099-01-10T12:00:00+00:00", "https://example/a", 80, "PT", "2026-01-01", "2026-01-02"),
            ("TED", "A-2", "Fechada", "Buyer B", "PRT", "2020-01-10T12:00:00+00:00", "https://example/b", 60, "PT", "2026-01-03", "2026-01-04"),
            ("BASE", "B-1", "Terceira", "Buyer C", "PRT", None, "https://example/c", 50, "PT", "2026-01-05", "2026-01-06"),
        ],
    )
    conn.commit()
    return conn


def test_save_is_idempotent_and_database_unique():
    conn = _conn()
    first = save_opportunity(conn, "empresa-a", 1)
    second = save_opportunity(conn, "empresa-a", 1)

    count = conn.execute(
        "SELECT COUNT(*) FROM opportunity_workflow WHERE account_id=? AND source=? AND external_id=?",
        ("empresa-a", "TED", "A-1"),
    ).fetchone()[0]
    assert count == 1
    assert first["saved_at"] == second["saved_at"]
    assert first["updated_at"] == second["updated_at"]
    assert second["priority"] == "NORMAL"
    assert second["status"] == "NEW"


def test_unsave_preserves_workflow_state_but_removes_watchlist_membership():
    conn = _conn()
    save_opportunity(conn, "empresa-a", 1)
    update_saved_opportunity(
        conn, "empresa-a", 1, status="REVIEWING", priority="HIGH", note="Falar com João", note_provided=True
    )

    assert unsave_opportunity(conn, "empresa-a", 1) is True
    assert get_saved_opportunity(conn, "empresa-a", 1) is None
    workflow = get_workflow(conn, "empresa-a", "TED", "A-1")
    assert workflow["is_saved"] is False
    assert workflow["status"] == "REVIEWING"
    assert workflow["priority"] == "HIGH"
    assert workflow["note"] == "Falar com João"


def test_tenant_isolation_read_write_delete_and_list():
    conn = _conn()
    save_opportunity(conn, "empresa-a", 1)

    assert get_saved_opportunity(conn, "empresa-b", 1) is None
    assert list_saved_opportunities(conn, "empresa-b") == []
    with pytest.raises(LookupError, match="saved_opportunity_not_found"):
        update_saved_opportunity(conn, "empresa-b", 1, priority="HIGH")
    assert unsave_opportunity(conn, "empresa-b", 1) is False
    assert get_saved_opportunity(conn, "empresa-a", 1)["is_saved"] is True


def test_update_status_priority_note_and_clear_note():
    conn = _conn()
    save_opportunity(conn, "empresa-a", 1)
    saved = update_saved_opportunity(
        conn,
        "empresa-a",
        1,
        status="REVIEWING",
        priority="HIGH",
        note="Falar com João sobre equipamento.",
        note_provided=True,
    )
    assert saved["status"] == "REVIEWING"
    assert saved["priority"] == "HIGH"
    assert saved["note"] == "Falar com João sobre equipamento."

    cleared = update_saved_opportunity(conn, "empresa-a", 1, note=None, note_provided=True)
    assert cleared["note"] is None
    assert cleared["saved_at"] == saved["saved_at"]
    assert cleared["updated_at"] >= saved["updated_at"]


def test_invalid_status_priority_note_and_empty_patch_are_rejected():
    conn = _conn()
    save_opportunity(conn, "empresa-a", 1)

    with pytest.raises(ValueError, match="invalid workflow status"):
        update_saved_opportunity(conn, "empresa-a", 1, status="HACKED")
    with pytest.raises(ValueError, match="invalid workflow priority"):
        update_saved_opportunity(conn, "empresa-a", 1, priority="URGENT")
    with pytest.raises(ValueError, match="note exceeds"):
        update_saved_opportunity(conn, "empresa-a", 1, note="x" * (NOTE_MAX_LENGTH + 1), note_provided=True)
    with pytest.raises(ValueError, match="no supported"):
        update_saved_opportunity(conn, "empresa-a", 1)


def test_missing_opportunity_cannot_be_saved():
    conn = _conn()
    with pytest.raises(LookupError, match="opportunity_not_found"):
        save_opportunity(conn, "empresa-a", 999)


def test_filter_order_pagination_and_closed_opportunity_are_deterministic():
    conn = _conn()
    save_opportunity(conn, "empresa-a", 1)
    save_opportunity(conn, "empresa-a", 2)
    save_opportunity(conn, "empresa-a", 3)
    update_saved_opportunity(conn, "empresa-a", 1, priority="LOW")
    update_saved_opportunity(conn, "empresa-a", 2, priority="HIGH", status="REVIEWING")

    high = list_saved_opportunities(conn, "empresa-a", priority="HIGH")
    assert [item["opportunity_id"] for item in high] == [2]
    reviewing = list_saved_opportunities(conn, "empresa-a", status="REVIEWING")
    assert [item["opportunity_id"] for item in reviewing] == [2]
    priority_order = list_saved_opportunities(conn, "empresa-a", order="priority")
    assert [item["priority"] for item in priority_order] == ["HIGH", "NORMAL", "LOW"]
    deadline_order = list_saved_opportunities(conn, "empresa-a", order="deadline")
    assert [item["opportunity_id"] for item in deadline_order[:2]] == [2, 1]
    page = list_saved_opportunities(conn, "empresa-a", order="priority", limit=1, offset=1)
    assert [item["opportunity_id"] for item in page] == [3]
    closed = next(item for item in priority_order if item["opportunity_id"] == 2)
    assert closed["deadline"].startswith("2020-")
    assert closed["opportunity_missing"] is False


def test_note_is_parameterized_and_does_not_mutate_schema():
    conn = _conn()
    save_opportunity(conn, "empresa-a", 1)
    hostile = "x'); DROP TABLE tenders; --"
    saved = update_saved_opportunity(conn, "empresa-a", 1, note=hostile, note_provided=True)
    assert saved["note"] == hostile
    assert conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0] == 3


def test_migrates_existing_workflow_table_without_data_loss():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE opportunity_workflow(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(account_id, source, external_id)
        )"""
    )
    conn.execute(
        "INSERT INTO opportunity_workflow(account_id, source, external_id, status, note, updated_at) VALUES(?,?,?,?,?,?)",
        ("empresa-a", "TED", "legacy", "REVIEWING", "preservar", "2026-01-01T00:00:00+00:00"),
    )
    conn.commit()

    ensure_workflow_table(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_workflow)").fetchall()}
    assert {"priority", "saved_at"}.issubset(columns)
    row = conn.execute("SELECT * FROM opportunity_workflow WHERE external_id='legacy'").fetchone()
    assert row["status"] == "REVIEWING"
    assert row["note"] == "preservar"
    assert row["priority"] == "NORMAL"
    assert row["saved_at"] is None


def _insert_api_opportunity():
    conn = app.db()
    try:
        conn.execute(
            """INSERT INTO tenders(source, external_id, title, country, deadline, url, first_seen, last_seen)
               VALUES('TED','API-1','API opportunity','PRT','2099-01-01T00:00:00+00:00','https://example/api','2026-01-01','2026-01-01')"""
        )
        conn.commit()
        return conn.execute("SELECT id FROM tenders WHERE source='TED' AND external_id='API-1'").fetchone()[0]
    finally:
        conn.close()


def test_api_save_update_list_unsave_and_account_derivation(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DB", str(tmp_path / "watchlist-api.db"))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "empresa-a")
    monkeypatch.setattr(
        account_registry,
        "subscription_state",
        lambda account: {"plan": "pilot", "active": True, "source": "test", "expires_at": None},
    )
    app.init_db()
    opportunity_id = _insert_api_opportunity()
    client = APP.test_client()

    saved = client.post(f"/api/v1/opportunities/{opportunity_id}/save", json={"account_id": "empresa-b"})
    assert saved.status_code == 200
    assert saved.get_json()["account_id"] == "empresa-a"
    first_saved_at = saved.get_json()["saved"]["saved_at"]

    duplicate = client.post(f"/api/v1/opportunities/{opportunity_id}/save")
    assert duplicate.status_code == 200
    assert duplicate.get_json()["saved"]["saved_at"] == first_saved_at

    updated = client.patch(
        f"/api/v1/opportunities/{opportunity_id}/watch",
        json={"status": "REVIEWING", "priority": "HIGH", "note": "Preparar visita"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["saved"]["priority"] == "HIGH"

    listed = client.get("/api/v1/opportunities/saved?priority=HIGH&order=priority&limit=10&offset=0")
    assert listed.status_code == 200
    assert listed.get_json()["count"] == 1
    assert listed.get_json()["items"][0]["opportunity_id"] == opportunity_id

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "empresa-b")
    assert client.get(f"/api/v1/opportunities/{opportunity_id}/watch").status_code == 404
    assert client.patch(f"/api/v1/opportunities/{opportunity_id}/watch", json={"priority": "LOW"}).status_code == 404
    assert client.delete(f"/api/v1/opportunities/{opportunity_id}/save").status_code == 404

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "empresa-a")
    removed = client.delete(f"/api/v1/opportunities/{opportunity_id}/save")
    assert removed.status_code == 200
    assert removed.get_json()["is_saved"] is False


def test_api_validation_and_auth_required(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DB", str(tmp_path / "watchlist-validation.db"))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "empresa-a")
    monkeypatch.setattr(
        account_registry,
        "subscription_state",
        lambda account: {"plan": "pilot", "active": True, "source": "test", "expires_at": None},
    )
    app.init_db()
    opportunity_id = _insert_api_opportunity()
    client = APP.test_client()
    assert client.post(f"/api/v1/opportunities/{opportunity_id}/save").status_code == 200

    assert client.patch(f"/api/v1/opportunities/{opportunity_id}/watch", json={"status": "INVALID"}).status_code == 400
    assert client.patch(f"/api/v1/opportunities/{opportunity_id}/watch", json={"priority": "URGENT"}).status_code == 400
    assert client.patch(f"/api/v1/opportunities/{opportunity_id}/watch", json={"note": "x" * (NOTE_MAX_LENGTH + 1)}).status_code == 400
    assert client.patch(f"/api/v1/opportunities/{opportunity_id}/watch", json={"account_id": "empresa-b"}).status_code == 400
    assert client.get("/api/v1/opportunities/saved?status=INVALID").status_code == 400
    assert client.get("/api/v1/opportunities/saved?priority=HIGH;DROP TABLE tenders").status_code == 400
    assert client.post("/api/v1/opportunities/999999/save").status_code == 404

    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://example.supabase.co")
    unauthorized = client.get("/api/v1/opportunities/saved")
    assert unauthorized.status_code == 401
    assert unauthorized.get_json()["error"] == "authentication_required"
