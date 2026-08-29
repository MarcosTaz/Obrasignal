from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
import re
from typing import Iterable


class TriggerTimingClass(str, Enum):
    EARLY_DIALOGUE = "early_dialogue"
    ACTIONABLE = "actionable"
    COMPRESSED = "compressed"
    TOO_LATE = "too_late"
    CLOSED = "closed"


@dataclass(frozen=True)
class TriggerWindow:
    published_on: date
    detected_on: date
    decision_deadline: date

    def validate(self) -> None:
        if self.detected_on < self.published_on:
            raise ValueError("detection date cannot precede publication")
        if self.decision_deadline < self.published_on:
            raise ValueError("decision deadline cannot precede publication")

    @property
    def detection_latency_days(self) -> int:
        self.validate()
        return (self.detected_on - self.published_on).days

    @property
    def days_remaining_at_detection(self) -> int:
        self.validate()
        return (self.decision_deadline - self.detected_on).days

    @property
    def timing_class(self) -> TriggerTimingClass:
        remaining = self.days_remaining_at_detection
        if remaining < 0:
            return TriggerTimingClass.CLOSED
        if remaining <= 3:
            return TriggerTimingClass.TOO_LATE
        if remaining <= 10:
            return TriggerTimingClass.COMPRESSED
        if remaining <= 30:
            return TriggerTimingClass.ACTIONABLE
        return TriggerTimingClass.EARLY_DIALOGUE

    @property
    def forecast_freeze_window_viable(self) -> bool:
        return self.timing_class in {
            TriggerTimingClass.EARLY_DIALOGUE,
            TriggerTimingClass.ACTIONABLE,
        }


def _normalized_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


@dataclass(frozen=True)
class TriggerRecord:
    """Public trigger observation separated from the underlying buyer decision event."""

    organization_id: str
    decision_event_id: str
    source_id: str
    notice_revision_id: str
    window: TriggerWindow

    def validate(self) -> None:
        if not all(
            str(value or "").strip()
            for value in (
                self.organization_id,
                self.decision_event_id,
                self.source_id,
                self.notice_revision_id,
            )
        ):
            raise ValueError("trigger identity fields are required")
        self.window.validate()

    @property
    def decision_event_key(self) -> str:
        self.validate()
        organization = _normalized_token(self.organization_id)
        event = _normalized_token(self.decision_event_id)
        if not organization or not event:
            raise ValueError("trigger identity cannot normalize to empty")
        return f"{organization}:{event}"


def deduplicate_decision_events(records: Iterable[TriggerRecord]) -> tuple[TriggerRecord, ...]:
    """Collapse notice revisions/sources without inflating acquisition volume.

    One organization + one switching/renewal decision event counts once. The
    representative observation is the earliest publication/detection, with stable
    source/revision tie-breaking. Notice revisions remain separate upstream truth;
    this helper exists only for commercial trigger-volume counting.
    """
    selected: dict[str, TriggerRecord] = {}
    for record in records:
        record.validate()
        key = record.decision_event_key
        current = selected.get(key)
        candidate_rank = (
            record.window.published_on,
            record.window.detected_on,
            record.source_id,
            record.notice_revision_id,
        )
        if current is None:
            selected[key] = record
            continue
        current_rank = (
            current.window.published_on,
            current.window.detected_on,
            current.source_id,
            current.notice_revision_id,
        )
        if candidate_rank < current_rank:
            selected[key] = record
    return tuple(selected[key] for key in sorted(selected))


def count_challengeable_decision_events(records: Iterable[TriggerRecord]) -> int:
    return sum(
        record.window.forecast_freeze_window_viable
        for record in deduplicate_decision_events(records)
    )
