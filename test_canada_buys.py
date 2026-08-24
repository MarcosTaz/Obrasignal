from datetime import datetime, timezone
import csv
from io import StringIO

import pytest

from canada_buys import (
    CSV_FIELDS,
    CanadaBuysCursor,
    _is_construction,
    _observation,
    _parse_csv,
    _state,
)


def _row(**updates):
    row = {field: "" for field in CSV_FIELDS}
    row.update({
        "title-titre-eng": "Bridge rehabilitation",
        "referenceNumber-numeroReference": "cb-1-123456",
        "amendmentNumber-numeroModification": "000",
        "solicitationNumber-numeroSollicitation": "PW-26-001/A",
        "publicationDate-datePublication": "2026-08-25",
        "tenderClosingDate-appelOffresDateCloture": "2026-09-10T13:00:00",
        "tenderStatus-appelOffresStatut-eng": "Open",
        "procurementCategory-categorieApprovisionnement": "*CNST",
        "unspsc": "*72141000",
        "regionsOfDelivery-regionsLivraison-eng": "*Ontario\n*Canada",
        "contractingEntityName-nomEntitContractante-eng": "Public Works",
        "noticeURL-URLavis-eng": "https://example.invalid/tender",
        "tenderDescription-descriptionAppelOffres-eng": "Rehabilitate bridge deck",
    })
    row.update(updates)
    return row


def _csv(rows, fields=CSV_FIELDS):
    out = StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def test_live_contract_has_67_publisher_columns():
    assert len(CSV_FIELDS) == 67
    parsed = _parse_csv(_csv([_row()]))
    assert len(parsed) == 1
    assert tuple(parsed[0]) == CSV_FIELDS


def test_schema_drift_fails_closed():
    with pytest.raises(RuntimeError, match="schema drift"):
        _parse_csv(_csv([_row()], fields=CSV_FIELDS[:-1]))


def test_construction_gate_is_publisher_native_not_keyword_based():
    assert _is_construction(_row()) is True
    assert _is_construction(_row(**{
        "title-titre-eng": "Construction of new depot",
        "procurementCategory-categorieApprovisionnement": "*GD",
    })) is False


def test_identity_is_solicitation_number_not_reference_number():
    first = _state(_row())
    amended = _state(_row(**{
        "referenceNumber-numeroReference": "cb-999-CHANGED",
        "amendmentNumber-numeroModification": "001",
        "amendmentDate-dateModification": "2026-08-26",
    }))
    assert first["external_id"] == "PW-26-001/A"
    assert amended["external_id"] == first["external_id"]
    assert amended["reference_number"] != first["reference_number"]
    assert amended["amendment_number"] == "001"


def test_closing_timestamp_uses_fixed_utc_minus_five_even_in_summer():
    state = _state(_row(**{
        "tenderClosingDate-appelOffresDateCloture": "2026-08-25T13:00:00",
    }))
    assert state["deadline"] == "2026-08-25T18:00:00Z"


def test_normalized_tender_does_not_fabricate_value_or_currency():
    state = _state(_row())
    obs = _observation(state)
    assert obs["external_id"] == "PW-26-001/A"
    assert obs["contract_type"] == "works"
    assert obs["value"] == ""
    assert obs["currency"] == ""
    assert obs["taxonomy"] == "UNSPSC"
    assert obs["category_code"] == "72141000"
    assert obs["place"] == "Ontario | Canada"


def test_cursor_roundtrip_preserves_conditional_validators_and_tracked_state():
    cursor = CanadaBuysCursor(
        tracked={"PW-26-001/A": _state(_row())},
        etag_new="new-etag",
        modified_new="Mon, 24 Aug 2026 22:15:16 GMT",
        etag_open="open-etag",
        modified_open="Mon, 24 Aug 2026 10:20:16 GMT",
        open_observed_at="2026-08-25T00:00:00Z",
    )
    decoded = CanadaBuysCursor.decode(cursor.encode())
    assert decoded.etag_new == "new-etag"
    assert decoded.etag_open == "open-etag"
    assert decoded.tracked["PW-26-001/A"]["external_id"] == "PW-26-001/A"


def test_missing_identity_or_closing_time_fails_closed():
    with pytest.raises(RuntimeError, match="solicitation number"):
        _state(_row(**{"solicitationNumber-numeroSollicitation": ""}))
    with pytest.raises(RuntimeError, match="closing timestamp"):
        _state(_row(**{"tenderClosingDate-appelOffresDateCloture": ""}))
