from datetime import datetime, timezone

from uk_find_tender import _dt, normalize_uk_record


def _record(deadline):
    return {
        "ocid": "ocds-temporal-uk",
        "compiledRelease": {
            "id": "compiled-current",
            "date": "2026-08-24T11:13:05+01:00",
            "tag": ["tender"],
            "buyer": {"name": "Temporal Buyer"},
            "tender": {
                "id": "temporal-tender",
                "title": "Temporal boundary tender",
                "description": "Construction works",
                "status": "active",
                "mainProcurementCategory": "works",
                "tenderPeriod": {"endDate": deadline},
                "items": [
                    {
                        "id": "1",
                        "classification": {"scheme": "CPV", "id": "45000000"},
                    }
                ],
            },
        },
        "releases": [
            {
                "id": "release-1",
                "date": "2026-08-24T11:13:05+01:00",
                "ocid": "ocds-temporal-uk",
            }
        ],
    }


def test_external_explicit_offsets_are_real_instants():
    assert _dt("2026-08-24T12:00:00Z") == datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    assert _dt("2026-08-24T13:00:00+01:00") == datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    assert _dt("2026-08-24T07:00:00-05:00") == datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def test_external_naive_datetime_remains_unknown_timezone():
    assert _dt("2026-08-24T12:00:00") is None


def test_external_malformed_or_missing_datetime_remains_unknown():
    assert _dt("not-a-time") is None
    assert _dt(None) is None


def test_naive_deadline_cannot_authoritatively_keep_tender_actionable():
    rows = normalize_uk_record(
        _record("2026-08-24T12:00:00"),
        now=datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc),
    )
    assert rows
    assert all(row["is_actionable"] is False for row in rows)
    assert all(row["lifecycle_status"] == "active_no_deadline" for row in rows)
