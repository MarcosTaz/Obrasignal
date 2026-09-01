from datetime import date, datetime, timezone

import pytest

from cloud_switching.procurement_timeline import NoticeRevision, ProcurementTimeline


def revision(deadline, observed_day, source):
    return NoticeRevision(
        notice_id="BGK-VMWARE-2026",
        observed_at=datetime(2026, 8, observed_day, 12, tzinfo=timezone.utc),
        published_on=date(2026, 7, 29),
        deadline=deadline,
        source_id=source,
    )


def test_latest_amended_deadline_is_preserved_without_erasing_history():
    timeline = ProcurementTimeline(
        revisions=(
            revision(date(2026, 8, 17), 1, "notice-original"),
            revision(date(2026, 8, 31), 12, "notice-amendment"),
        )
    )
    assert timeline.current_deadline == date(2026, 8, 31)
    assert timeline.deadline_history == (date(2026, 8, 17), date(2026, 8, 31))
    assert timeline.deadline_changed is True


def test_repeat_observation_does_not_create_fake_deadline_change():
    timeline = ProcurementTimeline(
        revisions=(
            revision(date(2026, 9, 7), 20, "mirror-a"),
            revision(date(2026, 9, 7), 21, "mirror-b"),
        )
    )
    assert timeline.deadline_history == (date(2026, 9, 7),)
    assert timeline.deadline_changed is False


def test_cross_notice_history_fails_closed():
    first = revision(date(2026, 8, 31), 12, "a")
    second = NoticeRevision(
        notice_id="OTHER",
        observed_at=datetime(2026, 8, 13, 12, tzinfo=timezone.utc),
        published_on=date(2026, 8, 1),
        deadline=date(2026, 9, 1),
        source_id="b",
    )
    with pytest.raises(ValueError, match="same canonical notice"):
        ProcurementTimeline((first, second)).current_deadline


def test_impossible_deadline_fails_closed():
    bad = NoticeRevision(
        notice_id="x",
        observed_at=datetime.now(timezone.utc),
        published_on=date(2026, 8, 20),
        deadline=date(2026, 8, 19),
        source_id="source",
    )
    with pytest.raises(ValueError, match="cannot precede publication"):
        ProcurementTimeline((bad,)).current_deadline
