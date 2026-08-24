from canada_buys import CSV_FIELDS, _state


def test_reference_change_does_not_change_canonical_identity():
    base = {field: "" for field in CSV_FIELDS}
    base.update({
        "title-titre-eng": "Construction package",
        "referenceNumber-numeroReference": "cb-100",
        "amendmentNumber-numeroModification": "000",
        "solicitationNumber-numeroSollicitation": "SOL-2026-1",
        "publicationDate-datePublication": "2026-08-25",
        "tenderClosingDate-appelOffresDateCloture": "2026-09-01T13:00:00",
        "tenderStatus-appelOffresStatut-eng": "Open",
        "procurementCategory-categorieApprovisionnement": "*CNST",
    })
    amended = dict(base)
    amended["referenceNumber-numeroReference"] = "cb-101"
    amended["amendmentNumber-numeroModification"] = "001"
    amended["amendmentDate-dateModification"] = "2026-08-26"

    assert _state(base)["external_id"] == _state(amended)["external_id"] == "SOL-2026-1"
