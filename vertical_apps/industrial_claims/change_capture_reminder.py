from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from vertical_apps.industrial_claims.change_capture import ChangeCaptureStore


class ChangeCaptureReminderError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: object, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChangeCaptureReminderError(f"invalid {label}") from exc
    if parsed.tzinfo is None:
        raise ChangeCaptureReminderError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


class ChangeCaptureReminderService:
    """Derive the smallest truthful reminder for the current sheet version.

    A reminder is satisfied only for the exact current SHA-256. Adding a fact
    changes that digest and automatically reactivates the prompt. All reminders
    terminate at factual-window close; this service never extends the window and
    never sends an external message by itself.
    """

    def __init__(
        self,
        database: str | Path,
        *,
        capture_store: ChangeCaptureStore,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.path = Path(database)
        self.capture_store = capture_store
        self.clock = clock

    def _current_export_count(self, *, tenant_id: str, finding_id: str, digest: str) -> int:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """SELECT COUNT(*) FROM causledger_change_sheet_downloads
                   WHERE tenant_id=? AND finding_id=? AND sheet_sha256=?""",
                (tenant_id, finding_id, digest),
            ).fetchone()
        return int(row[0])

    @staticmethod
    def _milestones(recorded_at: datetime, closes_at: datetime) -> list[tuple[str, datetime]]:
        candidates = [
            ("INITIAL", recorded_at),
            ("T_MINUS_24H", closes_at - timedelta(hours=24)),
            ("T_MINUS_4H", closes_at - timedelta(hours=4)),
            ("T_MINUS_1H", closes_at - timedelta(hours=1)),
        ]
        unique: list[tuple[str, datetime]] = []
        last: datetime | None = None
        for name, moment in sorted(candidates, key=lambda item: item[1]):
            if moment < recorded_at or moment >= closes_at:
                continue
            if last is not None and moment == last:
                continue
            unique.append((name, moment))
            last = moment
        return unique

    def status(self, *, tenant_id: str, finding_id: str) -> dict[str, Any]:
        capture = self.capture_store.status(tenant_id=tenant_id, finding_id=finding_id)
        sheet, digest = self.capture_store.render_sheet(tenant_id=tenant_id, finding_id=finding_id)
        if not sheet or len(digest) != 64:
            raise ChangeCaptureReminderError("current change sheet snapshot is invalid")
        current = self.clock()
        if current.tzinfo is None:
            raise ChangeCaptureReminderError("reminder clock must be timezone-aware")
        current = current.astimezone(timezone.utc)
        recorded_at = _aware(capture["recorded_at"], label="recorded_at")
        closes_at = _aware(capture["factual_window_closes_at"], label="factual_window_closes_at")
        export_count = self._current_export_count(
            tenant_id=tenant_id,
            finding_id=finding_id,
            digest=digest,
        )
        milestones = self._milestones(recorded_at, closes_at)
        next_milestone = next(((name, at) for name, at in milestones if at > current), None)
        most_recent_due = None
        for name, at in milestones:
            if at <= current:
                most_recent_due = (name, at)

        if current >= closes_at:
            state = "CLOSED"
            should_prompt = False
            message = "Factual input is closed. The contemporaneous download reminder has ended."
        elif export_count > 0:
            state = "SATISFIED_CURRENT_SNAPSHOT"
            should_prompt = False
            message = "The current hashed change sheet version has already been exported."
        else:
            state = "ACTIVE"
            should_prompt = True
            if closes_at - current <= timedelta(hours=1):
                message = "Final hour: download the current change sheet before factual input closes."
            elif closes_at - current <= timedelta(hours=4):
                message = "Factual input closes soon. Review the one-sentence change record and download the current sheet."
            else:
                message = "Describe the requested change and download the current hashed change sheet."

        return {
            "state": state,
            "should_prompt": should_prompt,
            "message": message,
            "current_sheet_sha256": digest,
            "current_snapshot_export_count": export_count,
            "current_snapshot_exported": export_count > 0,
            "recorded_at": recorded_at.isoformat(),
            "factual_window_closes_at": closes_at.isoformat(),
            "seconds_until_close": max(0, int((closes_at - current).total_seconds())),
            "most_recent_due_milestone": None if most_recent_due is None else {
                "name": most_recent_due[0], "at": most_recent_due[1].isoformat()
            },
            "next_milestone": None if next_milestone is None else {
                "name": next_milestone[0], "at": next_milestone[1].isoformat()
            },
            "milestones": [{"name": name, "at": at.isoformat()} for name, at in milestones],
            "reminder_terminates_at_factual_close": True,
            "new_fact_reactivates_reminder_by_changing_digest": True,
            "external_delivery_performed": False,
            "external_delivery_requires_separately_configured_authorized_channel": True,
        }
