from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from vertical_apps.industrial_claims.proof_externalization_audit import (
    ProofExternalizationAuditError,
    ProofExternalizationAuditStore,
)


NOW = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
TARGET = "a" * 64


def _store(database):
    return ProofExternalizationAuditStore(database, clock=lambda: NOW)


def test_externalization_operation_records_started_then_exactly_one_terminal_event(tmp_path):
    store = _store(tmp_path / "audit.sqlite3")
    started = store.start(
        tenant_id="tenant-a",
        finding_id="finding-a",
        actor_id="operator-a",
        target_sha256=TARGET,
        payload={"provider_kinds": ["QUALIFIED_TIMESTAMP", "QUALIFIED_SEAL"]},
    )
    assert started["state"] == "STARTED"
    completed = store.finish(
        operation_id=started["operation_id"],
        tenant_id="tenant-a",
        finding_id="finding-a",
        actor_id="operator-a",
        state="COMPLETED",
        target_sha256=TARGET,
        payload={"provider_states": {"QUALIFIED_TIMESTAMP": "VERIFIED"}},
    )
    assert completed["previous_event_hash"] == started["event_hash"]
    status = store.status(tenant_id="tenant-a", finding_id="finding-a")
    assert status["chain_valid"] is True
    assert status["event_count"] == 2
    assert [item["state"] for item in status["operations"][started["operation_id"]]] == ["STARTED", "COMPLETED"]

    with pytest.raises(ProofExternalizationAuditError, match="already closed"):
        store.finish(
            operation_id=started["operation_id"],
            tenant_id="tenant-a",
            finding_id="finding-a",
            actor_id="operator-a",
            state="FAILED",
            target_sha256=TARGET,
        )


def test_terminal_event_cannot_change_tenant_actor_finding_or_target(tmp_path):
    store = _store(tmp_path / "scope.sqlite3")
    started = store.start(
        tenant_id="tenant-a", finding_id="finding-a", actor_id="operator-a", target_sha256=TARGET
    )
    attempts = [
        {"tenant_id": "tenant-b", "finding_id": "finding-a", "actor_id": "operator-a", "target_sha256": TARGET},
        {"tenant_id": "tenant-a", "finding_id": "finding-b", "actor_id": "operator-a", "target_sha256": TARGET},
        {"tenant_id": "tenant-a", "finding_id": "finding-a", "actor_id": "operator-b", "target_sha256": TARGET},
        {"tenant_id": "tenant-a", "finding_id": "finding-a", "actor_id": "operator-a", "target_sha256": "b" * 64},
    ]
    for attempt in attempts:
        with pytest.raises(ProofExternalizationAuditError):
            store.finish(
                operation_id=started["operation_id"],
                state="COMPLETED",
                **attempt,
            )


def test_sqlite_update_and_delete_are_blocked(tmp_path):
    database = tmp_path / "append.sqlite3"
    store = _store(database)
    started = store.start(
        tenant_id="tenant-a", finding_id="finding-a", actor_id="operator-a", target_sha256=TARGET
    )
    with sqlite3.connect(database) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "UPDATE causledger_proof_externalization_events SET state='COMPLETED' WHERE event_id=?",
                (started["event_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "DELETE FROM causledger_proof_externalization_events WHERE event_id=?",
                (started["event_id"],),
            )


def test_hash_chain_detects_tampering_even_if_database_triggers_are_removed(tmp_path):
    database = tmp_path / "tamper.sqlite3"
    store = _store(database)
    started = store.start(
        tenant_id="tenant-a", finding_id="finding-a", actor_id="operator-a", target_sha256=TARGET,
        payload={"provider_kinds": ["QUALIFIED_TIMESTAMP"]},
    )
    store.finish(
        operation_id=started["operation_id"],
        tenant_id="tenant-a", finding_id="finding-a", actor_id="operator-a",
        state="FAILED", target_sha256=TARGET, payload={"error_type": "SyntheticFailure"},
    )
    with sqlite3.connect(database) as conn:
        conn.execute("DROP TRIGGER causledger_proof_externalization_no_update")
        conn.execute(
            "UPDATE causledger_proof_externalization_events SET payload_json='{}' WHERE event_id=?",
            (started["event_id"],),
        )
    with pytest.raises(ProofExternalizationAuditError, match="event hash mismatch"):
        store.status(tenant_id="tenant-a", finding_id="finding-a")
