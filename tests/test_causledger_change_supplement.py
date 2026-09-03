from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from vertical_apps.industrial_claims.change_capture import ChangeCaptureStore
from vertical_apps.industrial_claims.change_supplement import ChangeSupplementError, LateChangeSupplementStore
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(database) -> str:
    result = IndustrialClaimsService(database).analyze(
        tenant_id="tenant-a",
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
        notice_due=date(2026, 9, 30),
    )
    return result.finding.finding_id


def _closed_capture(database, finding):
    now = [datetime.now(timezone.utc)]
    capture = ChangeCaptureStore(database, clock=lambda: now[0])
    open_status = capture.status(tenant_id="tenant-a", finding_id=finding)
    now[0] = datetime.fromisoformat(open_status["factual_window_closes_at"]) + timedelta(seconds=1)
    return capture, now


def test_late_supplement_is_rejected_while_contemporaneous_window_is_open(tmp_path):
    database = tmp_path / "open.sqlite3"
    finding = _case(database)
    capture = ChangeCaptureStore(database)
    supplements = LateChangeSupplementStore(database, capture_store=capture)

    with pytest.raises(ChangeSupplementError, match="only available after"):
        supplements.add(
            tenant_id="tenant-a",
            finding_id=finding,
            actor_id="client-a",
            fact_text="Late-looking information while normal capture is still open.",
            reason_for_late_entry="Should use the normal factual capture instead.",
        )


def test_late_supplement_after_close_does_not_change_original_sheet_or_reopen_reminder(tmp_path):
    database = tmp_path / "closed.sqlite3"
    finding = _case(database)
    capture, now = _closed_capture(database, finding)
    original_sheet, original_digest = capture.render_sheet(tenant_id="tenant-a", finding_id=finding)
    supplements = LateChangeSupplementStore(database, capture_store=capture, clock=lambda: now[0])

    item = supplements.add(
        tenant_id="tenant-a",
        finding_id=finding,
        actor_id="client-a",
        fact_text="A customer meeting note was located after the normal factual window closed.",
        reason_for_late_entry="Meeting minutes were received from project archive after close.",
        source_ref="meeting-minutes-2026-08-30",
        declared_event_at="2026-08-30T15:00:00+01:00",
    )
    assert item["classification"] == "LATE_SUPPLEMENT"
    assert item["declared_event_at"] == "2026-08-30T14:00:00+00:00"

    after_sheet, after_digest = capture.render_sheet(tenant_id="tenant-a", finding_id=finding)
    assert after_digest == original_digest
    assert after_sheet == original_sheet
    capture_status = capture.status(tenant_id="tenant-a", finding_id=finding)
    assert capture_status["window_state"] == "CLOSED"
    assert capture_status["download_prompt"]["active"] is False

    supplement_status = supplements.status(tenant_id="tenant-a", finding_id=finding)
    assert supplement_status["available"] is True
    assert supplement_status["count"] == 1
    assert supplement_status["late_supplement_does_not_reopen_contemporaneous_window"] is True
    rendered, digest = supplements.render_sheet(tenant_id="tenant-a", finding_id=finding)
    assert "LATE_SUPPLEMENT" in rendered
    assert "does not rewrite, extend, or backdate" in rendered
    assert digest in rendered


def test_late_supplement_declared_event_time_must_be_timezone_aware(tmp_path):
    database = tmp_path / "timezone.sqlite3"
    finding = _case(database)
    capture, now = _closed_capture(database, finding)
    supplements = LateChangeSupplementStore(database, capture_store=capture, clock=lambda: now[0])

    with pytest.raises(ChangeSupplementError, match="must include timezone"):
        supplements.add(
            tenant_id="tenant-a",
            finding_id=finding,
            actor_id="client-a",
            fact_text="Information located later.",
            reason_for_late_entry="Archive delay.",
            declared_event_at="2026-08-30T15:00:00",
        )


def test_late_supplement_chain_is_append_only(tmp_path):
    database = tmp_path / "append.sqlite3"
    finding = _case(database)
    capture, now = _closed_capture(database, finding)
    supplements = LateChangeSupplementStore(database, capture_store=capture, clock=lambda: now[0])
    item = supplements.add(
        tenant_id="tenant-a",
        finding_id=finding,
        actor_id="client-a",
        fact_text="A delayed source was found.",
        reason_for_late_entry="Archive delivered it after close.",
    )

    with sqlite3.connect(database) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "UPDATE causledger_change_late_supplements SET fact_text='rewritten' WHERE supplement_id=?",
                (item["supplement_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "DELETE FROM causledger_change_late_supplements WHERE supplement_id=?",
                (item["supplement_id"],),
            )
