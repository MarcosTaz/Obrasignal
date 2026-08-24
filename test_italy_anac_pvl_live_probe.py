"""TEMPORARY live smoke for IT_ANAC. Delete before merge."""
from datetime import date, datetime, timezone

from italy_anac_pvl import ANACPVLConnector, _notice_events, _dt


def test_anac_pvl_live_archive_exposes_actionable_works_lots():
    connector = ANACPVLConnector(
        page_size=100,
        max_pages_per_day=20,
        max_items_per_day=2000,
        timeout=60,
    )
    pub_day = date(2026, 8, 18)
    rows = connector._fetch_day(pub_day)
    assert rows, "ANAC PVL archive day unexpectedly empty"

    events = []
    for payload in rows:
        events.extend(_notice_events(payload, publication_day=pub_day.isoformat()))

    works = [event for event in events if event.get("is_works")]
    assert works, "ANAC PVL live day returned no publisher-native Lavori lots"
    assert all(event.get("external_id") for event in works)
    assert all(event.get("notice_id") and event.get("procedure_id") for event in works)

    reference = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    actionable = [event for event in works if event.get("active") and not event.get("obscured") and _dt(event.get("deadline")) and _dt(event.get("deadline")) > reference]
    assert actionable, "ANAC PVL live day returned no Lavori lot with a future structured deadline"

    # CPV in this PVL payload is observed as publisher label text; do not assert
    # or manufacture a numeric CPV code.
    assert any(event.get("cpv_label") for event in actionable)
