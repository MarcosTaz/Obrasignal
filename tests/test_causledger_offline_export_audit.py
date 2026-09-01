from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from vertical_apps.industrial_claims.offline_export_audit import (
    OfflineExportAuditError,
    OfflineExportAuditStore,
)


NOW = datetime(2026, 9, 1, 21, 0, tzinfo=timezone.utc)
TARGET = "a" * 64
BUNDLE = "b" * 64


def _store(tmp_path):
    return OfflineExportAuditStore(
        tmp_path / "offline-export-audit.sqlite3",
        clock=lambda: NOW,
    )


def test_offline_export_audit_is_append_only_hash_chained_and_metadata_only(tmp_path):
    store = _store(tmp_path)
    started = store.start(
        tenant_id="tenant-a",
        finding_id="tenant-a:finding-1",
        actor_id="reviewer-a",
        target_sha256=TARGET,
        evidence_count=4,
    )
    completed = store.finish(
        operation_id=started["operation_id"],
        tenant_id="tenant-a",
        finding_id="tenant-a:finding-1",
        actor_id="reviewer-a",
        target_sha256=TARGET,
        state="COMPLETED",
        payload={
            "evidence_count": 4,
            "bundle_sha256": BUNDLE,
            "independent_verification_valid": True,
            "contains_documentary_bytes": False,
        },
    )

    status = store.status(tenant_id="tenant-a", finding_id="tenant-a:finding-1")
    assert status["event_count"] == 2
    assert status["chain_valid"] is True
    assert status["append_only"] is True
    assert status["documentary_content_stored"] is False
    events = status["operations"][started["operation_id"]]
    assert [event["state"] for event in events] == ["STARTED", "COMPLETED"]
    assert events[0]["previous_event_hash"] is None
    assert events[1]["previous_event_hash"] == started["event_hash"]
    assert completed["event_hash"] == status["chain_head_sha256"]
    assert events[1]["payload"]["bundle_sha256"] == BUNDLE
    assert "content" not in json.dumps(status).lower()

    with sqlite3.connect(store.path) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "UPDATE causledger_offline_export_events SET actor_id='attacker' WHERE operation_id=?",
                (started["operation_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "DELETE FROM causledger_offline_export_events WHERE operation_id=?",
                (started["operation_id"],),
            )


def test_offline_export_audit_refuses_documentary_or_unbounded_metadata(tmp_path):
    store = _store(tmp_path)
    started = store.start(
        tenant_id="tenant-a",
        finding_id="tenant-a:finding-1",
        actor_id="reviewer-a",
        target_sha256=TARGET,
        evidence_count=4,
    )
    with pytest.raises(OfflineExportAuditError, match="unsupported metadata"):
        store.finish(
            operation_id=started["operation_id"],
            tenant_id="tenant-a",
            finding_id="tenant-a:finding-1",
            actor_id="reviewer-a",
            target_sha256=TARGET,
            state="COMPLETED",
            payload={
                "content_base64": "SECRET-DOCUMENT",
                "contains_documentary_bytes": False,
            },
        )
    status = store.status(tenant_id="tenant-a", finding_id="tenant-a:finding-1")
    assert status["event_count"] == 1
    assert status["operations"][started["operation_id"]][0]["state"] == "STARTED"


def test_offline_export_audit_detects_hash_chain_tampering_even_if_sql_triggers_are_removed(tmp_path):
    store = _store(tmp_path)
    started = store.start(
        tenant_id="tenant-a",
        finding_id="tenant-a:finding-1",
        actor_id="reviewer-a",
        target_sha256=TARGET,
        evidence_count=4,
    )
    store.finish(
        operation_id=started["operation_id"],
        tenant_id="tenant-a",
        finding_id="tenant-a:finding-1",
        actor_id="reviewer-a",
        target_sha256=TARGET,
        state="FAILED",
        payload={
            "failure_class": "AssuranceStoreError",
            "contains_documentary_bytes": False,
        },
    )
    with sqlite3.connect(store.path) as conn:
        conn.execute("DROP TRIGGER causledger_offline_export_no_update")
        conn.execute("DROP TRIGGER causledger_offline_export_no_delete")
        conn.execute(
            "UPDATE causledger_offline_export_events SET actor_id='attacker' WHERE operation_id=? AND state='STARTED'",
            (started["operation_id"],),
        )
        conn.commit()

    with pytest.raises(OfflineExportAuditError, match="event hash mismatch"):
        store.status(tenant_id="tenant-a", finding_id="tenant-a:finding-1")
