from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from vertical_apps.industrial_claims.change_capture import ChangeCaptureStore
from vertical_apps.industrial_claims.change_capture_reminder import ChangeCaptureReminderService
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


def test_reminder_is_satisfied_only_for_current_exported_snapshot_and_reactivates_after_fact(tmp_path):
    database = tmp_path / "reminder.sqlite3"
    finding = _case(database)
    now = [datetime.now(timezone.utc)]
    capture = ChangeCaptureStore(database, clock=lambda: now[0])
    first = capture.status(tenant_id="tenant-a", finding_id=finding)
    now[0] = datetime.fromisoformat(first["recorded_at"]) + timedelta(minutes=1)
    reminders = ChangeCaptureReminderService(database, capture_store=capture, clock=lambda: now[0])

    initial = reminders.status(tenant_id="tenant-a", finding_id=finding)
    assert initial["state"] == "ACTIVE"
    assert initial["should_prompt"] is True
    assert initial["current_snapshot_exported"] is False
    assert initial["reminder_terminates_at_factual_close"] is True

    _sheet, digest = capture.render_sheet(tenant_id="tenant-a", finding_id=finding)
    capture.record_download(
        tenant_id="tenant-a",
        finding_id=finding,
        actor_id="client-a",
        sheet_sha256=digest,
    )
    satisfied = reminders.status(tenant_id="tenant-a", finding_id=finding)
    assert satisfied["state"] == "SATISFIED_CURRENT_SNAPSHOT"
    assert satisfied["should_prompt"] is False
    assert satisfied["current_snapshot_export_count"] == 1

    capture.add_fact(
        tenant_id="tenant-a",
        finding_id=finding,
        actor_id="client-a",
        fact_type="REQUESTED_CHANGE",
        fact_text="Move mounting holes 8 mm.",
        source_ref="customer-email-1",
    )
    reactivated = reminders.status(tenant_id="tenant-a", finding_id=finding)
    assert reactivated["current_sheet_sha256"] != satisfied["current_sheet_sha256"]
    assert reactivated["state"] == "ACTIVE"
    assert reactivated["should_prompt"] is True
    assert reactivated["new_fact_reactivates_reminder_by_changing_digest"] is True


def test_reminder_terminates_exactly_at_factual_close_even_if_current_sheet_was_never_exported(tmp_path):
    database = tmp_path / "reminder-close.sqlite3"
    finding = _case(database)
    now = [datetime.now(timezone.utc)]
    capture = ChangeCaptureStore(database, clock=lambda: now[0])
    status = capture.status(tenant_id="tenant-a", finding_id=finding)
    reminders = ChangeCaptureReminderService(database, capture_store=capture, clock=lambda: now[0])

    now[0] = datetime.fromisoformat(status["factual_window_closes_at"]) + timedelta(microseconds=1)
    closed = reminders.status(tenant_id="tenant-a", finding_id=finding)
    assert closed["state"] == "CLOSED"
    assert closed["should_prompt"] is False
    assert closed["seconds_until_close"] == 0
    assert closed["current_snapshot_exported"] is False
    assert closed["external_delivery_performed"] is False


def test_reminder_milestones_are_inside_fixed_window_and_do_not_extend_it(tmp_path):
    database = tmp_path / "reminder-milestones.sqlite3"
    finding = _case(database)
    capture = ChangeCaptureStore(database)
    status = capture.status(tenant_id="tenant-a", finding_id=finding)
    recorded = datetime.fromisoformat(status["recorded_at"])
    closes = datetime.fromisoformat(status["factual_window_closes_at"])
    reminders = ChangeCaptureReminderService(database, capture_store=capture, clock=lambda: recorded + timedelta(minutes=1))

    reminder = reminders.status(tenant_id="tenant-a", finding_id=finding)
    assert reminder["factual_window_closes_at"] == closes.astimezone(timezone.utc).isoformat()
    assert all(recorded <= datetime.fromisoformat(item["at"]) < closes for item in reminder["milestones"])
    assert {item["name"] for item in reminder["milestones"]} == {"INITIAL", "T_MINUS_24H", "T_MINUS_4H", "T_MINUS_1H"}
