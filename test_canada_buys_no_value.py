from canada_buys import CSV_FIELDS, _observation, _state


def test_tender_notice_contract_leaves_value_unknown():
    row = {field: "" for field in CSV_FIELDS}
    row.update({
        "title-titre-eng": "Civil works",
        "referenceNumber-numeroReference": "cb-200",
        "solicitationNumber-numeroSollicitation": "SOL-200",
        "publicationDate-datePublication": "2026-08-25",
        "tenderClosingDate-appelOffresDateCloture": "2026-09-15T13:00:00",
        "tenderStatus-appelOffresStatut-eng": "Open",
        "procurementCategory-categorieApprovisionnement": "*CNST",
    })
    observation = _observation(_state(row))
    assert observation["value"] == ""
    assert observation["currency"] == ""
