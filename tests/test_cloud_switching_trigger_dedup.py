from datetime import date

from cloud_switching.triggers import (
    TriggerRecord,
    TriggerWindow,
    count_challengeable_decision_events,
    deduplicate_decision_events,
)


def _record(org, event, source, revision, published, detected, deadline):
    return TriggerRecord(
        organization_id=org,
        decision_event_id=event,
        source_id=source,
        notice_revision_id=revision,
        window=TriggerWindow(
            published_on=date.fromisoformat(published),
            detected_on=date.fromisoformat(detected),
            decision_deadline=date.fromisoformat(deadline),
        ),
    )


def test_notice_revisions_and_multiple_sources_count_as_one_decision_event():
    records = (
        _record("City A", "vmware-replacement-2026", "TED", "r1", "2026-08-01", "2026-08-02", "2026-09-20"),
        _record("City A", "vmware-replacement-2026", "national", "r2", "2026-08-01", "2026-08-03", "2026-09-25"),
        _record("City B", "virtualization-renewal-2026", "TED", "r1", "2026-08-05", "2026-08-06", "2026-09-15"),
    )
    deduped = deduplicate_decision_events(records)
    assert len(deduped) == 2
    assert {item.decision_event_key for item in deduped} == {
        "city-a:vmware-replacement-2026",
        "city-b:virtualization-renewal-2026",
    }


def test_challengeable_volume_counts_deduplicated_early_and_actionable_only():
    records = (
        _record("Buyer A", "event-1", "TED", "r1", "2026-08-01", "2026-08-02", "2026-09-20"),
        _record("Buyer A", "event-1", "TED", "r2", "2026-08-01", "2026-08-04", "2026-09-18"),
        _record("Buyer B", "event-2", "TED", "r1", "2026-08-20", "2026-08-21", "2026-09-10"),
        _record("Buyer C", "event-3", "TED", "r1", "2026-08-20", "2026-08-28", "2026-08-31"),
    )
    assert count_challengeable_decision_events(records) == 2
