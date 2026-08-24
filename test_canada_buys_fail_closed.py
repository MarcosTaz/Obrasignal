import pytest

from canada_buys import CSV_FIELDS, _state


def _base():
    row = {field: "" for field in CSV_FIELDS}
    row.update({
        "title-titre-eng": "Construction",
        "referenceNumber-numeroReference": "cb-300",
        "solicitationNumber-numeroSollicitation": "SOL-300",
        "publicationDate-datePublication": "2026-08-25",
        "tenderClosingDate-appelOffresDateCloture": "2026-09-15T13:00:00",
        "tenderStatus-appelOffresStatut-eng": "Open",
        "procurementCategory-categorieApprovisionnement": "*CNST",
    })
    return row


def test_missing_solicitation_fails_closed():
    row = _base()
    row["solicitationNumber-numeroSollicitation"] = ""
    with pytest.raises(RuntimeError, match="solicitation number"):
        _state(row)


def test_invalid_closing_time_fails_closed():
    row = _base()
    row["tenderClosingDate-appelOffresDateCloture"] = "not-a-date"
    with pytest.raises(RuntimeError, match="closing timestamp"):
        _state(row)
