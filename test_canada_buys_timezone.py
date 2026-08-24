from canada_buys import CSV_FIELDS, _state


def test_august_closing_uses_publisher_fixed_minus_five_not_dst():
    row = {field: "" for field in CSV_FIELDS}
    row.update({
        "title-titre-eng": "Works",
        "referenceNumber-numeroReference": "cb-400",
        "solicitationNumber-numeroSollicitation": "SOL-400",
        "publicationDate-datePublication": "2026-08-25",
        "tenderClosingDate-appelOffresDateCloture": "2026-08-25T13:00:00",
        "tenderStatus-appelOffresStatut-eng": "Open",
        "procurementCategory-categorieApprovisionnement": "*CNST",
    })
    assert _state(row)["deadline"] == "2026-08-25T18:00:00Z"
