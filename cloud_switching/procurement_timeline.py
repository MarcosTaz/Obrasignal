from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class NoticeRevision:
    notice_id: str
    observed_at: datetime
    published_on: date
    deadline: date | None
    source_id: str

    def validate(self) -> None:
        if not self.notice_id.strip() or not self.source_id.strip():
            raise ValueError("notice_id and source_id are required")
        if self.deadline is not None and self.deadline < self.published_on:
            raise ValueError("deadline cannot precede publication")


@dataclass(frozen=True)
class ProcurementTimeline:
    revisions: tuple[NoticeRevision, ...]

    def validate(self) -> None:
        if not self.revisions:
            raise ValueError("at least one notice revision is required")
        for revision in self.revisions:
            revision.validate()
        if len({r.notice_id for r in self.revisions}) != 1:
            raise ValueError("all revisions must belong to the same canonical notice")
        observed = [r.observed_at for r in self.revisions]
        if observed != sorted(observed):
            raise ValueError("notice revisions must be ordered by observation time")

    @property
    def current_deadline(self) -> date | None:
        self.validate()
        for revision in reversed(self.revisions):
            if revision.deadline is not None:
                return revision.deadline
        return None

    @property
    def deadline_history(self) -> tuple[date, ...]:
        self.validate()
        result: list[date] = []
        for revision in self.revisions:
            if revision.deadline is not None and (not result or result[-1] != revision.deadline):
                result.append(revision.deadline)
        return tuple(result)

    @property
    def deadline_changed(self) -> bool:
        return len(self.deadline_history) > 1
