import pytest

from serbia_procurement_probe import (
    SOURCE_ID,
    SerbiaExportSchemaError,
    incremental_cursor,
    normalize_export_record,
    probe_summary,
)


def test_construction_cpv_and_stable_identity():
    raw = {
        "procedureId": "2026-RS-001",
        "type": "tender",
        "title": "Reconstruction of municipal road",
        "cpvCodes": ["45233120-6", "71300000-1"],
        "publicationDate": "2026-08-20T09:00:00Z",
        "lastModified": "2026-08-21T10:00:00Z",
        "buyerId": "BUYER-17",
        "lotId": "LOT-1",
    }
    one = normalize_export_record(raw)
    two = normalize_export_record(dict(raw))
    assert one.is_construction is True
    assert one.logical_id == two.logical_id
    assert one.source_id == SOURCE_ID
    assert one.signal_type == "TENDER"


def test_non_construction_not_promoted_by_title_keyword():
    item = normalize_export_record({
        "procedureId": "P-2",
        "type": "tender",
        "title": "Construction consultancy wording must not override CPV",
        "cpvCode": "72000000-5",
    })
    assert item.is_construction is False


def test_plan_award_contract_and_amendment_are_canonical_types():
    base = {"procedureId": "P", "title": "x", "cpvCode": "45000000-7"}
    assert normalize_export_record({**base, "type": "plan"}).signal_type == "PROCUREMENT_PLAN"
    assert normalize_export_record({**base, "type": "award"}).signal_type == "AWARD"
    assert normalize_export_record({**base, "type": "contract"}).signal_type == "CONTRACT"
    assert normalize_export_record({**base, "type": "contract amendment"}).signal_type == "AMENDMENT"


def test_unknown_type_fails_closed():
    with pytest.raises(SerbiaExportSchemaError):
        normalize_export_record({"procedureId": "P", "title": "x", "type": "mystery"})


def test_missing_stable_identity_fails_closed():
    with pytest.raises(SerbiaExportSchemaError):
        normalize_export_record({"title": "x", "type": "tender"})


def test_incremental_cursor_uses_publisher_timestamp_only():
    first = normalize_export_record({
        "procedureId": "P1", "title": "x", "type": "tender",
        "publicationDate": "2026-08-20T09:00:00Z",
    })
    second = normalize_export_record({
        "procedureId": "P2", "title": "y", "type": "award",
        "publicationDate": "2026-08-20T10:00:00Z",
        "lastModified": "2026-08-22T11:00:00Z",
    })
    assert incremental_cursor([first, second]) == "2026-08-22T11:00:00Z"


def test_probe_never_claims_production_ready():
    summary = probe_summary([{
        "procedureId": "P1", "title": "Works", "type": "tender", "cpvCode": "45000000-7"
    }])
    assert summary["production_ready"] is False
    assert summary["construction_records"] == 1
