import copy
import sqlite3

import pytest

from procurement_lineage import (
    detect_lineage_relations,
    ensure_lineage_tables,
    lineage_view,
    persist_lineage_relations,
)


def rec(external_id, signal_type="TENDER", **extra):
    row = {
        "source": "TEST",
        "external_id": external_id,
        "signal_type": signal_type,
        "title": extra.pop("title", "Bridge rehabilitation"),
        "buyer": extra.pop("buyer", "Public Works Agency"),
        "country": extra.pop("country", "PT"),
        "published_at": extra.pop("published_at", None),
    }
    row.update(extra)
    return row


def edge_types(result):
    return {(e["from_entity_type"], e["relationship_type"], e["to_entity_type"]) for e in result["confirmed_relations"]}


def test_explicit_plan_to_tender_relation():
    plan = rec("plan-1", "PROCUREMENT_PLAN")
    tender = rec("tender-1", lineage_relations=[{"target_external_id": "plan-1", "native_relation_type": "previousNotice"}])
    result = detect_lineage_relations([plan, tender])
    assert ("PROCUREMENT_PLAN", "PRECEDES", "TENDER") in edge_types(result)
    assert result["confirmed_relations"][0]["basis"] == "EXPLICIT"


def test_explicit_tender_to_award_and_award_to_contract():
    tender = rec("t-1")
    award = rec("a-1", "AWARD", lineage_relations=[{"target_external_id": "t-1"}])
    contract = rec("c-1", "CONTRACT", lineage_relations=[{"target_external_id": "a-1"}])
    result = detect_lineage_relations([tender, award, contract])
    assert ("TENDER", "RESULTED_IN", "AWARD") in edge_types(result)
    assert ("AWARD", "CONTRACTED_AS", "CONTRACT") in edge_types(result)


def test_amendment_and_corrigendum_explicit_targets():
    tender = rec("t-1")
    amendment = rec("am-1", lineage_node_type="AMENDMENT", lineage_relations=[{
        "target_external_id": "t-1", "relationship_type": "AMENDS", "target_is_parent": False
    }])
    corrigendum = rec("co-1", lineage_node_type="CORRIGENDUM", lineage_relations=[{
        "target_external_id": "t-1", "relationship_type": "CORRECTS", "target_is_parent": False
    }])
    result = detect_lineage_relations([tender, amendment, corrigendum])
    assert ("AMENDMENT", "AMENDS", "TENDER") in edge_types(result)
    assert ("CORRIGENDUM", "CORRECTS", "TENDER") in edge_types(result)


def test_same_ocid_links_distinct_lifecycle_stages_deterministically():
    tender = rec("t-1", ocid="ocds-x-123")
    award = rec("a-1", "AWARD", ocid="ocds-x-123")
    result = detect_lineage_relations([tender, award])
    assert len(result["confirmed_relations"]) == 1
    assert result["confirmed_relations"][0]["basis"] == "DETERMINISTIC"
    assert result["confirmed_relations"][0]["reasons"] == ["same OCDS OCID"]


def test_same_stage_same_ocid_is_change_history_not_lineage():
    first = rec("t-v1", ocid="ocds-x-123")
    second = rec("t-v2", ocid="ocds-x-123")
    assert detect_lineage_relations([first, second])["confirmed_relations"] == []


def test_same_title_different_buyer_does_not_link():
    one = rec("one", title="Same title", buyer="Buyer A", buyer_id="A")
    two = rec("two", "AWARD", title="Same title", buyer="Buyer B", buyer_id="B")
    result = detect_lineage_relations([one, two])
    assert result["confirmed_relations"] == []
    assert result["candidates"] == []


def test_same_buyer_different_official_procurement_does_not_confirm():
    one = rec("one", buyer_id="BUYER-1", procurement_reference="PROC-A")
    two = rec("two", "AWARD", buyer_id="BUYER-1", procurement_reference="PROC-B")
    result = detect_lineage_relations([one, two])
    assert result["confirmed_relations"] == []


def test_same_value_and_location_do_not_link():
    one = rec("one", value="100000", place="Lisbon")
    two = rec("two", "AWARD", value="100000", place="Lisbon")
    assert detect_lineage_relations([one, two])["confirmed_relations"] == []


def test_same_buyer_adjacent_dates_do_not_link_without_second_signal():
    one = rec("one", buyer="Buyer A", published_at="2026-01-01")
    two = rec("two", "AWARD", buyer="Buyer A", published_at="2026-01-02", title="Different title")
    result = detect_lineage_relations([one, two])
    assert result["confirmed_relations"] == []
    assert result["candidates"] == []


def test_cross_source_explicit_reference_is_preserved():
    plan = rec("plan-1", "PROCUREMENT_PLAN", source="SOURCE_A")
    tender = rec("t-1", source="SOURCE_B", lineage_relations=[{
        "target_source": "SOURCE_A", "target_external_id": "plan-1", "source_ref": "official-cross-ref"
    }])
    result = detect_lineage_relations([plan, tender])
    edge = result["confirmed_relations"][0]
    assert edge["basis"] == "EXPLICIT"
    assert edge["source_ref"] == "official-cross-ref"


def test_cross_source_without_strong_identity_remains_candidate():
    one = rec("one", source="SOURCE_A", buyer_id="B-1", title="Same title")
    two = rec("two", "AWARD", source="SOURCE_B", buyer_id="B-1", title="Same title")
    result = detect_lineage_relations([one, two])
    assert result["confirmed_relations"] == []
    assert result["candidates"][0]["status"] == "UNRESOLVED"


def test_same_official_reference_in_jurisdiction_is_deterministic():
    one = rec("one", procurement_reference="PROC-77", jurisdiction="PT")
    two = rec("two", "AWARD", procurement_reference="PROC-77", jurisdiction="PT")
    result = detect_lineage_relations([one, two])
    assert result["confirmed_relations"][0]["basis"] == "DETERMINISTIC"


def test_multiple_awards_and_contracts_are_one_to_many():
    tender = rec("t", ocid="ocds-1")
    a1 = rec("a1", "AWARD", ocid="ocds-1", lot_id="L1")
    a2 = rec("a2", "AWARD", ocid="ocds-1", lot_id="L2")
    c1 = rec("c1", "CONTRACT", ocid="ocds-1", lot_id="L1")
    c2 = rec("c2", "CONTRACT", ocid="ocds-1", lot_id="L2")
    result = detect_lineage_relations([tender, a1, a2, c1, c2])
    edges = result["confirmed_relations"]
    assert any(e["to_entity_id"] == "TEST:a1" for e in edges)
    assert any(e["to_entity_id"] == "TEST:a2" for e in edges)
    assert any(e["from_entity_id"] == "TEST:a1" and e["to_entity_id"] == "TEST:c1" for e in edges)
    assert any(e["from_entity_id"] == "TEST:a2" and e["to_entity_id"] == "TEST:c2" for e in edges)
    assert not any(e["from_entity_id"] == "TEST:a1" and e["to_entity_id"] == "TEST:c2" for e in edges)


def test_cross_lot_explicit_edge_is_rejected():
    a1 = rec("a1", "AWARD", lot_id="L1")
    c2 = rec("c2", "CONTRACT", lot_id="L2", lineage_relations=[{"target_external_id": "a1"}])
    with pytest.raises(ValueError, match="cross-lot"):
        detect_lineage_relations([a1, c2])


def test_cancelled_tender_remains_in_lineage():
    tender = rec("t", ocid="ocds-1", is_actionable=False, lifecycle_status="cancelled")
    award = rec("a", "AWARD", ocid="ocds-1")
    result = detect_lineage_relations([tender, award])
    assert len(result["confirmed_relations"]) == 1


def test_retender_not_automatically_linked_by_same_buyer_and_title():
    old = rec("old", buyer_id="B", title="Road works", procurement_reference="OLD")
    new = rec("new", buyer_id="B", title="Road works", procurement_reference="NEW")
    result = detect_lineage_relations([old, new])
    assert result["confirmed_relations"] == []


def test_missing_dates_retained_in_read_model():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    tender = rec("t", ocid="ocds-1", published_at=None)
    award = rec("a", "AWARD", ocid="ocds-1", published_at="2026-03-01")
    persist_lineage_relations(conn, [tender, award])
    view = lineage_view(conn, entity_id="TEST:t")
    assert len(view["timeline"]) == 2
    assert any(item["date_known"] is False for item in view["timeline"])


def test_cycle_is_rejected_but_explicit_override_order_is_deterministic():
    a = rec("a")
    b = rec("b", lineage_relations=[{
        "target_external_id": "a", "relationship_type": "SUPERSEDES", "target_is_parent": False
    }])
    a["lineage_relations"] = [{
        "target_external_id": "b", "relationship_type": "SUPERSEDES", "target_is_parent": False
    }]
    result = detect_lineage_relations([a, b])
    assert len(result["confirmed_relations"]) == 1
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["reason"] == "cycle prevented"


def test_duplicate_edge_persistence_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    tender = rec("t", ocid="ocds-1")
    award = rec("a", "AWARD", ocid="ocds-1")
    first = persist_lineage_relations(conn, [tender, award])
    second = persist_lineage_relations(conn, [tender, award])
    assert first["edges_inserted"] == 1
    assert second["edges_inserted"] == 0
    assert conn.execute("SELECT COUNT(*) FROM procurement_lineage_edges").fetchone()[0] == 1


def test_detector_is_deterministic_and_does_not_mutate_inputs():
    rows = [
        rec("p", "PROCUREMENT_PLAN", ocid="ocds-1"),
        rec("t", ocid="ocds-1"),
        rec("a", "AWARD", ocid="ocds-1"),
    ]
    original = copy.deepcopy(rows)
    first = detect_lineage_relations(rows)
    second = detect_lineage_relations(list(reversed(rows)))
    assert first["confirmed_relations"] == second["confirmed_relations"]
    assert rows == original


def test_adding_unrelated_record_does_not_change_confirmed_lineage():
    base = [rec("t", ocid="ocds-1"), rec("a", "AWARD", ocid="ocds-1")]
    before = detect_lineage_relations(base)["confirmed_relations"]
    unrelated = rec("x", "AWARD", buyer="Other", buyer_id="OTHER", procurement_reference="OTHER")
    after = detect_lineage_relations(base + [unrelated])["confirmed_relations"]
    assert before == after


def test_explicit_relation_precedes_weak_heuristic():
    plan = rec("p", "PROCUREMENT_PLAN", buyer_id="B", title="Same")
    tender = rec("t", buyer_id="B", title="Same", lineage_relations=[{"target_external_id": "p"}])
    result = detect_lineage_relations([plan, tender])
    assert len(result["confirmed_relations"]) == 1
    assert result["confirmed_relations"][0]["basis"] == "EXPLICIT"
    assert result["candidates"] == []


def test_oversized_identifier_fails_closed():
    with pytest.raises(ValueError, match="safety limit"):
        detect_lineage_relations([rec("x" * 600)])


def test_malformed_relation_type_fails_closed():
    tender = rec("t")
    award = rec("a", "AWARD", lineage_relations=[{
        "target_external_id": "t", "relationship_type": "DROP TABLE"
    }])
    with pytest.raises(ValueError, match="unsupported lineage relationship"):
        detect_lineage_relations([tender, award])


def test_sqlish_ids_are_data_not_sql():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    weird = rec("x'); DROP TABLE procurement_lineage_nodes; --")
    persist_lineage_relations(conn, [weird])
    assert conn.execute("SELECT COUNT(*) FROM procurement_lineage_nodes").fetchone()[0] == 1


def test_ensure_tables_is_idempotent():
    conn = sqlite3.connect(":memory:")
    ensure_lineage_tables(conn)
    ensure_lineage_tables(conn)
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='procurement_lineage_edges'").fetchone()[0] == 1
