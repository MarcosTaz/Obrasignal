from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from vertical_apps.industrial_claims.change_capture import ChangeCaptureError, ChangeCaptureStore
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(database, tenant: str = "tenant-a") -> str:
    service = IndustrialClaimsService(database)
    result = service.analyze(
        tenant_id=tenant,
        actor_id="analyst-a",
        customer_ref="oem-a",
        program_ref="program-a",
        event_ref="ECO-017",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-1",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="commercial basis",
        event_evidence_content="customer requested engineering change",
        cost_evidence_content="engineering cost record",
        notice_due=datetime(2026, 9, 30, tzinfo=timezone.utc).date(),
    )
    return result.finding.finding_id


def test_change_capture_window_is_fixed_from_first_case_record_and_cannot_be_extended(tmp_path):
    database = tmp_path / "change.sqlite3"
    finding = _case(database)
    now = [datetime.now(timezone.utc)]
    store = ChangeCaptureStore(database, clock=lambda: now[0])
    status = store.status(tenant_id="tenant-a", finding_id=finding)
    recorded = datetime.fromisoformat(status["recorded_at"])
    closes = datetime.fromisoformat(status["factual_window_closes_at"])
    assert closes - recorded == timedelta(hours=72)
    assert status["window_state"] == "OPEN"
    assert status["download_prompt"]["active"] is True
    assert status["truth_boundary"]["operational_capture_window_is_not_contractual_notice_deadline"] is True

    with pytest.raises(ChangeCaptureError, match="cannot be silently changed"):
        store.ensure_window(tenant_id="tenant-a", finding_id=finding, factual_window_hours=96)


def test_simple_change_sheet_records_request_and_declared_time_without_calling_it_certified(tmp_path):
    database = tmp_path / "sheet.sqlite3"
    finding = _case(database)
    store = ChangeCaptureStore(database)
    store.add_fact(
        tenant_id="tenant-a",
        finding_id=finding,
        actor_id="client-user",
        fact_type="REQUESTED_CHANGE",
        fact_text="Move bracket hole pattern 8 mm to clear the revised housing.",
        source_ref="customer-email-2026-08-31",
    )
    store.add_fact(
        tenant_id="tenant-a",
        finding_id=finding,
        actor_id="client-user",
        fact_type="CHANGE_REQUESTED_AT",
        fact_text="2026-08-31T14:35:00+01:00",
        source_ref="customer-email-2026-08-31",
    )
    status = store.status(tenant_id="tenant-a", finding_id=finding)
    assert status["requested_change"].startswith("Move bracket hole pattern")
    assert status["requested_change_source"] == "DECLARED_FACT"
    assert status["declared_change_requested_at"] == "2026-08-31T13:35:00+00:00"
    assert status["declared_change_requested_at_is_externally_verified"] is False

    sheet, digest = store.render_sheet(tenant_id="tenant-a", finding_id=finding)
    assert "CAUSLEDGER — CHANGE CAPTURE SHEET" in sheet
    assert "Move bracket hole pattern 8 mm" in sheet
    assert "2026-08-31T13:35:00+00:00" in sheet
    assert "does not prove customer responsibility" in sheet
    assert digest in sheet


def test_factual_entry_stops_exactly_when_window_has_expired_but_sheet_remains_downloadable(tmp_path):
    database = tmp_path / "closed.sqlite3"
    finding = _case(database)
    current = [datetime.now(timezone.utc)]
    store = ChangeCaptureStore(database, clock=lambda: current[0])
    open_status = store.status(tenant_id="tenant-a", finding_id=finding)
    current[0] = datetime.fromisoformat(open_status["factual_window_closes_at"]) + timedelta(seconds=1)

    closed = store.status(tenant_id="tenant-a", finding_id=finding)
    assert closed["window_state"] == "CLOSED"
    assert closed["fact_entry_allowed"] is False
    assert closed["download_prompt"]["active"] is False
    with pytest.raises(ChangeCaptureError, match="window is closed"):
        store.add_fact(
            tenant_id="tenant-a",
            finding_id=finding,
            actor_id="client-user",
            fact_type="OTHER_FACT",
            fact_text="attempted late factual insertion",
        )
    sheet, digest = store.render_sheet(tenant_id="tenant-a", finding_id=finding)
    assert "Factual window status at download: CLOSED" in sheet
    assert digest in sheet


def test_fact_history_and_download_receipts_are_append_only(tmp_path):
    database = tmp_path / "append.sqlite3"
    finding = _case(database)
    store = ChangeCaptureStore(database)
    fact = store.add_fact(
        tenant_id="tenant-a",
        finding_id=finding,
        actor_id="client-user",
        fact_type="OTHER_FACT",
        fact_text="Line stopped for fixture rework.",
    )
    sheet, digest = store.render_sheet(tenant_id="tenant-a", finding_id=finding)
    receipt = store.record_download(
        tenant_id="tenant-a",
        finding_id=finding,
        actor_id="client-user",
        sheet_sha256=digest,
    )
    assert receipt["sheet_sha256"] == digest
    assert "Line stopped for fixture rework" in sheet
    assert store.status(tenant_id="tenant-a", finding_id=finding)["download_count"] == 1

    with sqlite3.connect(database) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "UPDATE causledger_change_facts SET fact_text='rewritten history' WHERE fact_id=?",
                (fact["fact_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "UPDATE causledger_change_sheet_downloads SET actor_id='attacker' WHERE download_id=?",
                (receipt["download_id"],),
            )


def test_change_capture_is_tenant_scoped_and_declared_timestamp_must_be_timezone_aware(tmp_path):
    database = tmp_path / "scope.sqlite3"
    finding = _case(database, tenant="tenant-a")
    store = ChangeCaptureStore(database)
    with pytest.raises(ChangeCaptureError, match="tenant-scoped industrial case not found"):
        store.status(tenant_id="tenant-b", finding_id=finding)
    with pytest.raises(ChangeCaptureError, match="must include timezone"):
        store.add_fact(
            tenant_id="tenant-a",
            finding_id=finding,
            actor_id="client-user",
            fact_type="CHANGE_REQUESTED_AT",
            fact_text="2026-08-31T14:35:00",
        )
