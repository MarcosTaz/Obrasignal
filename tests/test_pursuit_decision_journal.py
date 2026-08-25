import sqlite3

import pytest

import api
import pursuit_decision_api
from pursuit_decision import (
    DecisionValidationError,
    IdempotencyConflict,
    current_decision,
    decision_history,
    ensure_pursuit_decision_table,
    record_pursuit_decision,
)
from pursuit_decision_presentation import present_pursuit_decision


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _database(path):
    def connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute('''CREATE TABLE IF NOT EXISTS tenders(
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
            external_id TEXT NOT NULL, title TEXT, deadline TEXT,
            publication_date TEXT, last_seen TEXT, score INTEGER,
            UNIQUE(source, external_id))''')
        conn.commit()
        return conn
    return connect


def _seed(connect):
    conn = connect()
    conn.execute(
        '''INSERT INTO tenders(id, source, external_id, title, deadline, publication_date, last_seen, score)
           VALUES(1, 'TED', 'X1', 'Bridge works', '2026-10-10', '2026-08-20', '2026-08-25', 88)'''
    )
    conn.commit()
    before = dict(conn.execute("SELECT * FROM tenders WHERE id=1").fetchone())
    conn.close()
    return before


def test_domain_states_history_supersession_current_reasons_notes_and_refs():
    conn = _conn()
    first, created = record_pursuit_decision(
        conn, account_id="company-a", opportunity_id=7, decision_type="HOLD",
        decided_at="2026-09-01T10:00:00+00:00",
        reason_codes=["INSUFFICIENT_INFORMATION"], freeform_note="Need evidence.",
        blockers=["Qualification"], unknowns=["Insurance"],
        readiness_ref="readiness:7:v1", evidence_refs=["evidence:abc"],
        opportunity_revision_ref="TED:X:rev-1",
        opportunity_state={"deadline": "2026-09-20"}, confidence=0.6,
    )
    second, _ = record_pursuit_decision(
        conn, account_id="company-a", opportunity_id=7, decision_type="PURSUE",
        decided_at="2026-09-05T09:00:00+00:00", reason_codes=["GOOD_FIT"],
    )
    assert created is True
    assert second["supersedes_decision_id"] == first["decision_id"]
    assert current_decision(conn, "company-a", 7)["decision_type"] == "PURSUE"
    history = decision_history(conn, "company-a", 7)
    assert [item["decision_type"] for item in history] == ["HOLD", "PURSUE"]
    assert history[0]["reason_codes"] == ["INSUFFICIENT_INFORMATION"]
    assert history[0]["freeform_note"] == "Need evidence."
    assert history[0]["readiness_ref"] == "readiness:7:v1"
    assert history[0]["evidence_refs"] == ["evidence:abc"]


def test_domain_accepts_all_v0_states_and_rejects_invalid_values():
    conn = _conn()
    for number, state in enumerate(("PURSUE", "NO_BID", "HOLD", "NEEDS_INFO", "UNDECIDED"), 1):
        item, _ = record_pursuit_decision(conn, account_id="a", opportunity_id=number, decision_type=state)
        assert item["decision_type"] == state
    with pytest.raises(DecisionValidationError):
        record_pursuit_decision(conn, account_id="a", opportunity_id=99, decision_type="READY")
    with pytest.raises(DecisionValidationError):
        record_pursuit_decision(conn, account_id="a", opportunity_id=99, decision_type="HOLD", reason_codes=["MADE_UP"])
    with pytest.raises(DecisionValidationError):
        record_pursuit_decision(conn, account_id="a", opportunity_id=99, decision_type="HOLD", decided_at="yesterday")
    with pytest.raises(DecisionValidationError):
        record_pursuit_decision(conn, account_id="a", opportunity_id=99, decision_type="HOLD", decided_at="2026-09-01T10:00:00")


def test_decided_at_is_normalized_for_chronological_ordering():
    conn = _conn()
    item, _ = record_pursuit_decision(
        conn, account_id="a", opportunity_id=8, decision_type="HOLD",
        decided_at="2026-09-01T12:00:00+02:00",
    )
    assert item["decided_at"] == "2026-09-01T10:00:00+00:00"


def test_domain_tenant_isolation_and_idempotency():
    conn = _conn()
    a, created = record_pursuit_decision(conn, account_id="a", opportunity_id=5, decision_type="PURSUE", idempotency_key="same")
    retry, retry_created = record_pursuit_decision(
        conn, account_id="a", opportunity_id=5, decision_type="PURSUE",
        opportunity_state={"score": 99}, opportunity_revision_ref="later", idempotency_key="same",
    )
    record_pursuit_decision(conn, account_id="b", opportunity_id=5, decision_type="NO_BID", idempotency_key="same")
    assert created is True and retry_created is False and retry["decision_id"] == a["decision_id"]
    assert current_decision(conn, "a", 5)["decision_type"] == "PURSUE"
    assert current_decision(conn, "b", 5)["decision_type"] == "NO_BID"
    with pytest.raises(IdempotencyConflict):
        record_pursuit_decision(conn, account_id="a", opportunity_id=5, decision_type="NO_BID", idempotency_key="same")


def test_write_path_serializes_current_read_and_append():
    conn = _conn()
    statements = []
    conn.set_trace_callback(statements.append)
    record_pursuit_decision(conn, account_id="a", opportunity_id=9, decision_type="HOLD")
    assert any(statement.strip().upper() == "BEGIN IMMEDIATE" for statement in statements)


def test_history_order_is_deterministic_while_current_follows_supersession():
    conn = _conn()
    later, _ = record_pursuit_decision(conn, account_id="a", opportunity_id=3, decision_type="HOLD", decided_at="2026-09-05T00:00:00+00:00")
    backdated, _ = record_pursuit_decision(conn, account_id="a", opportunity_id=3, decision_type="NEEDS_INFO", decided_at="2026-09-01T00:00:00+00:00", actor_type="IMPORTED")
    assert backdated["supersedes_decision_id"] == later["decision_id"]
    assert current_decision(conn, "a", 3)["decision_id"] == backdated["decision_id"]
    assert [x["decision_type"] for x in decision_history(conn, "a", 3)] == ["NEEDS_INFO", "HOLD"]


def test_schema_migration_is_idempotent_and_preserves_rows():
    conn = _conn()
    ensure_pursuit_decision_table(conn)
    first, _ = record_pursuit_decision(conn, account_id="a", opportunity_id=1, decision_type="HOLD")
    ensure_pursuit_decision_table(conn)
    row = conn.execute("SELECT decision_id FROM opportunity_pursuit_decisions WHERE account_id='a'").fetchone()
    assert row["decision_id"] == first["decision_id"]
    indexes = {row[1] for row in conn.execute("PRAGMA index_list(opportunity_pursuit_decisions)")}
    assert {"idx_pursuit_decision_current", "idx_pursuit_decision_supersedes"} <= indexes


def test_presentation_is_contextual_not_dashboard():
    result = present_pursuit_decision({"decision_type": "PURSUE"}, [{"decision_type": "HOLD"}])
    assert result["title"] == "YOUR DECISION"
    assert [item["value"] for item in result["actions"]] == ["PURSUE", "HOLD", "NO_BID", "NEEDS_INFO"]


def test_api_create_supersede_read_history_and_does_not_mutate_opportunity(monkeypatch, tmp_path):
    connect = _database(tmp_path / "decision.db")
    before = _seed(connect)
    monkeypatch.setattr(pursuit_decision_api, "_db", connect)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-a")
    client = api.APP.test_client()
    hold = client.post(
        "/api/v1/opportunities/1/decision", headers={"Idempotency-Key": "hold-1"},
        json={"decision_type": "HOLD", "reason_codes": ["INSUFFICIENT_INFORMATION"],
              "note": "Need insurance", "readiness_ref": "readiness:1:v2",
              "evidence_refs": ["evidence:one"]},
    )
    assert hold.status_code == 201
    pursue = client.post(
        "/api/v1/opportunities/1/decision", headers={"Idempotency-Key": "pursue-1"},
        json={"decision_type": "PURSUE", "reason_codes": ["GOOD_FIT"]},
    )
    assert pursue.status_code == 201
    assert pursue.get_json()["decision"]["supersedes_decision_id"] == hold.get_json()["decision"]["decision_id"]
    assert client.get("/api/v1/opportunities/1/decision").get_json()["decision"]["decision_type"] == "PURSUE"
    history = client.get("/api/v1/opportunities/1/decisions").get_json()["items"]
    assert [item["decision_type"] for item in history] == ["HOLD", "PURSUE"]
    assert history[0]["readiness_ref"] == "readiness:1:v2"
    assert history[0]["evidence_refs"] == ["evidence:one"]
    conn = connect()
    after = dict(conn.execute("SELECT * FROM tenders WHERE id=1").fetchone())
    conn.close()
    assert after == before


def test_api_tenant_isolation_invalid_missing_and_idempotent_retry(monkeypatch, tmp_path):
    connect = _database(tmp_path / "api.db")
    _seed(connect)
    monkeypatch.setattr(pursuit_decision_api, "_db", connect)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    client = api.APP.test_client()
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-a")
    headers = {"Idempotency-Key": "retry-1"}
    payload = {"decision_type": "NO_BID", "reason_codes": ["MARGIN_CONCERN"]}
    first = client.post("/api/v1/opportunities/1/decision", headers=headers, json=payload)
    assert first.status_code == 201
    first_id = first.get_json()["decision"]["decision_id"]
    first_snapshot = first.get_json()["decision"]["opportunity_state"]
    conn = connect()
    conn.execute("UPDATE tenders SET score=42, last_seen='2026-08-26' WHERE id=1")
    conn.commit()
    conn.close()
    retry = client.post("/api/v1/opportunities/1/decision", headers=headers, json=payload)
    assert retry.status_code == 200
    assert retry.get_json()["created"] is False
    assert retry.get_json()["decision"]["decision_id"] == first_id
    assert retry.get_json()["decision"]["opportunity_state"] == first_snapshot
    assert client.post("/api/v1/opportunities/1/decision", json={"decision_type": "READY"}).status_code == 400
    assert client.post("/api/v1/opportunities/1/decision", json={"decision_type": "HOLD", "decided_at": "not-a-date"}).status_code == 400
    assert client.post("/api/v1/opportunities/1/decision", json={"decision_type": "HOLD", "actor_type": "SYSTEM_SUGGESTED"}).status_code == 400
    assert client.post("/api/v1/opportunities/999/decision", json={"decision_type": "PURSUE"}).status_code == 404
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-b")
    assert client.post("/api/v1/opportunities/1/decision", json={"decision_type": "NEEDS_INFO"}).status_code == 201
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "company-a")
    assert client.get("/api/v1/opportunities/1/decision").get_json()["decision"]["decision_type"] == "NO_BID"
    conflict = client.post("/api/v1/opportunities/1/decision", headers=headers, json={"decision_type": "PURSUE"})
    assert conflict.status_code == 409
