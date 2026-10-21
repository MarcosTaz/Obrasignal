from datetime import datetime, timezone

import pytest

from uk_find_tender_lifecycle import (
    UKFindTenderLifecycleConnector,
    _releases_requiring_current_tender_hydration,
)
from uk_find_tender_planning import (
    UKPlanningSchemaError,
    normalize_uk3_release,
    normalize_uk3_releases,
)


def _uk3_release(
    *,
    release_id="016962-2026",
    ocid="ocds-h6vhtk-0512ab",
    date="2026-02-25T14:45:00Z",
    tag="planning",
    category="works",
    cpv="45000000",
    future_notice="2026-04-01T23:59:59Z",
    title="Codi Group Construction Framework",
):
    return {
        "ocid": ocid,
        "id": release_id,
        "date": date,
        "tag": [tag],
        "buyer": {"id": "GB-PPON-PABC-1234-ABCD", "name": "Codi Group Ltd"},
        "planning": {
            "documents": [
                {
                    "id": release_id,
                    "documentType": "plannedProcurementNotice",
                    "noticeType": "UK3",
                    "url": f"https://www.find-tender.service.gov.uk/Notice/{release_id}",
                }
            ]
        },
        "tender": {
            "legalBasis": {"id": "2023/54", "scheme": "UKPGA"},
            "title": title,
            "description": "Future construction framework",
            "mainProcurementCategory": category,
            "value": {"amount": 8000000, "currency": "GBP"},
            "communication": {"futureNoticeDate": future_notice},
            "items": [
                {
                    "id": "1",
                    "additionalClassifications": [
                        {"scheme": "CPV", "id": cpv, "description": "Construction work"}
                    ],
                }
            ],
            "lots": [
                {
                    "id": "1",
                    "contractPeriod": {
                        "startDate": "2026-07-01T00:00:00Z",
                        "endDate": "2030-06-30T23:59:59Z",
                    },
                }
            ],
        },
    }


def test_uk3_construction_notice_becomes_procurement_plan_not_tender():
    row = normalize_uk3_release(_uk3_release())
    assert row["source"] == "UK_PROCUREMENT"
    assert row["signal_type"] == "PROCUREMENT_PLAN"
    assert row["external_id"] == "ocds-h6vhtk-0512ab:notice:UK3"
    assert row["source_reference"] == "016962-2026"
    assert row["notice_type"] == "UK3"
    assert row["target_date"] == "2026-04-01"
    assert row["deadline"] is None
    assert row["value"] == "8000000"
    assert row["currency"] == "GBP"
    assert row["category_code"] == "45000000"
    assert row["buyer"] == "Codi Group Ltd"
    assert row["construction_relevant"] is True


def test_uk3_edit_reuses_logical_identity_and_latest_version_wins():
    first = _uk3_release(release_id="010000-2026", date="2026-01-10T09:00:00Z")
    edited = _uk3_release(
        release_id="016962-2026",
        date="2026-02-25T14:45:00Z",
        tag="planningUpdate",
        future_notice="2026-05-01T23:59:59Z",
    )
    rows = normalize_uk3_releases([edited, first])
    assert len(rows) == 1
    assert rows[0]["external_id"] == "ocds-h6vhtk-0512ab:notice:UK3"
    assert rows[0]["source_reference"] == "016962-2026"
    assert rows[0]["target_date"] == "2026-05-01"


def test_non_construction_uk3_is_healthy_empty_not_source_error():
    assert normalize_uk3_release(_uk3_release(category="services", cpv="72000000")) is None
    assert normalize_uk3_releases([_uk3_release(category="services", cpv="72000000")]) == []


def test_uk2_is_not_guessed_into_procurement_plan():
    release = _uk3_release()
    release["planning"]["documents"][0]["noticeType"] = "UK2"
    release["planning"]["documents"][0]["documentType"] = "marketEngagementNotice"
    assert normalize_uk3_release(release) is None


def test_uk3_document_identity_and_type_drift_fail_closed():
    release = _uk3_release()
    release["planning"]["documents"][0]["id"] = "different"
    with pytest.raises(UKPlanningSchemaError, match="does not match release id"):
        normalize_uk3_release(release)

    release = _uk3_release()
    release["planning"]["documents"][0]["documentType"] = "tenderNotice"
    with pytest.raises(UKPlanningSchemaError, match="documentType contract changed"):
        normalize_uk3_release(release)


def test_wrong_legal_basis_or_unsafe_url_fail_closed():
    release = _uk3_release()
    release["tender"]["legalBasis"]["id"] = "legacy"
    with pytest.raises(UKPlanningSchemaError, match="Procurement Act 2023"):
        normalize_uk3_release(release)

    release = _uk3_release()
    release["planning"]["documents"][0]["url"] = "https://example.invalid/notice"
    with pytest.raises(UKPlanningSchemaError, match="unsafe"):
        normalize_uk3_release(release)


def test_equal_timestamp_conflicting_versions_fail_closed():
    a = _uk3_release(release_id="010000-2026")
    b = _uk3_release(release_id="020000-2026", title="Different title")
    with pytest.raises(UKPlanningSchemaError, match="conflicting UK3 versions"):
        normalize_uk3_releases([a, b])


def test_planning_only_ocid_is_not_hydrated_as_tender():
    planning = _uk3_release()
    assert _releases_requiring_current_tender_hydration([planning]) == []


def test_nonplanning_release_preserves_existing_hydration_path_for_same_ocid():
    planning = _uk3_release()
    tender = {
        "ocid": planning["ocid"],
        "id": "020000-2026",
        "date": "2026-04-01T12:00:00Z",
        "tag": ["tender"],
    }
    rows = _releases_requiring_current_tender_hydration([planning, tender])
    assert rows == [planning, tender]


def test_unknown_or_missing_tag_preserves_previous_fail_closed_hydration_behavior():
    release = _uk3_release()
    release.pop("tag")
    assert _releases_requiring_current_tender_hydration([release]) == [release]


class _NoHydrationSession:
    def get(self, *args, **kwargs):
        raise AssertionError("planning-only window must not issue a record hydration request")


def test_planning_only_window_returns_plan_without_record_hydration():
    connector = UKFindTenderLifecycleConnector(session=_NoHydrationSession())
    rows = connector._process_release_window(
        [_uk3_release()],
        start=datetime(2026, 2, 25, 14, 30, tzinfo=timezone.utc),
        end=datetime(2026, 2, 25, 15, 0, tzinfo=timezone.utc),
        now=datetime(2026, 2, 25, 15, 0, tzinfo=timezone.utc),
    )
    assert len(rows) == 1
    assert rows[0]["signal_type"] == "PROCUREMENT_PLAN"
