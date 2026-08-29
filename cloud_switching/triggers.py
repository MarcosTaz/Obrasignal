from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


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
