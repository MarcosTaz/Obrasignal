from procurement_lineage import detect_lineage_relations


def rec(external_id, *, node_type="TENDER", **extra):
    row = {
        "source": "TEST",
        "external_id": external_id,
        "signal_type": "TENDER",
        "lineage_node_type": node_type,
        "title": "Works",
        "buyer": "Buyer",
        "country": "PT",
    }
    row.update(extra)
    return row


def only_edge(records):
    result = detect_lineage_relations(records)
    assert len(result["confirmed_relations"]) == 1
    return result["confirmed_relations"][0]


def test_amends_defaults_from_amendment_to_target():
    tender = rec("tender")
    amendment = rec(
        "amendment",
        node_type="AMENDMENT",
        lineage_relations=[{
            "target_external_id": "tender",
            "relationship_type": "AMENDS",
        }],
    )
    edge = only_edge([tender, amendment])
    assert edge["from_entity_id"] == "TEST:amendment"
    assert edge["to_entity_id"] == "TEST:tender"


def test_corrects_defaults_from_corrigendum_to_target():
    tender = rec("tender")
    corrigendum = rec(
        "corrigendum",
        node_type="CORRIGENDUM",
        lineage_relations=[{
            "target_external_id": "tender",
            "relationship_type": "CORRECTS",
        }],
    )
    edge = only_edge([tender, corrigendum])
    assert edge["from_entity_id"] == "TEST:corrigendum"
    assert edge["to_entity_id"] == "TEST:tender"


def test_supersedes_defaults_from_new_notice_to_previous_notice():
    previous = rec("previous")
    replacement = rec(
        "replacement",
        lineage_relations=[{
            "target_external_id": "previous",
            "relationship_type": "SUPERSEDES",
        }],
    )
    edge = only_edge([previous, replacement])
    assert edge["from_entity_id"] == "TEST:replacement"
    assert edge["to_entity_id"] == "TEST:previous"


def test_parent_result_relation_defaults_from_target_to_current():
    tender = rec("tender")
    award = rec(
        "award",
        node_type="AWARD",
        lineage_relations=[{
            "target_external_id": "tender",
            "relationship_type": "RESULTED_IN",
        }],
    )
    edge = only_edge([tender, award])
    assert edge["from_entity_id"] == "TEST:tender"
    assert edge["to_entity_id"] == "TEST:award"


def test_adapter_direction_override_remains_available():
    parent = rec("parent")
    child = rec(
        "child",
        lineage_relations=[{
            "target_external_id": "parent",
            "relationship_type": "RELATED_TO",
            "target_is_parent": False,
        }],
    )
    edge = only_edge([parent, child])
    assert edge["from_entity_id"] == "TEST:child"
    assert edge["to_entity_id"] == "TEST:parent"
