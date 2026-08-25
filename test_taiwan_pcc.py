import sqlite3

import pytest

from signal_store import persist_signal_records
from taiwan_pcc import (
    PCCSnapshotSource,
    TaiwanPCCPreparedConnector,
    normalize_pcc_row,
    parse_snapshot_xml,
    production_gate_reasons,
)


PLAN_XML = """<?xml version='1.0' encoding='UTF-8'?>
<root>
  <row>
    <標案案號>A-2026-001</標案案號>
    <標案名稱>道路改善工程</標案名稱>
    <機關名稱>測試市政府</機關名稱>
    <招標方式>公開招標</招標方式>
    <預定招標年月>115/09</預定招標年月>
  </row>
</root>
"""

RECRUITMENT_XML = """<root><row>
<Tender_number>A-2026-001</Tender_number>
<Project_name>道路改善工程</Project_name>
<Agency_name>測試市政府</Agency_name>
<The_number_of_announcements>2</The_number_of_announcements>
<Date_of_public_solicitation>2026-08-25</Date_of_public_solicitation>
</row></root>"""


def test_parse_snapshot_preserves_native_identity_and_text():
    rows = parse_snapshot_xml(PLAN_XML)
    assert len(rows) == 1
    source = PCCSnapshotSource(6574, "procurement_notice", "PROCUREMENT_PLAN", "https://example.invalid")
    record = normalize_pcc_row(rows[0], source=source, observed_at="2026-08-25T00:00:00+00:00")
    assert record["source"] == "TW_PCC"
    assert record["signal_type"] == "PROCUREMENT_PLAN"
    assert record["external_id"] == "procurement_plan:A-2026-001"
    assert record["source_reference"] == "A-2026-001"
    assert record["lineage_key"] == "A-2026-001"
    assert record["title"] == "道路改善工程"
    assert record["buyer"] == "測試市政府"
    assert record["target_date"] == "2026-09-01"  # ROC year 115 -> 2026


def test_lineage_key_survives_signal_stage_change_without_identity_collision():
    plan_source = PCCSnapshotSource(6574, "procurement_notice", "PROCUREMENT_PLAN", "https://example.invalid")
    dialogue_source = PCCSnapshotSource(7261, "public_recruitment_announcement", "MARKET_DIALOGUE", "https://example.invalid")
    plan = normalize_pcc_row(parse_snapshot_xml(PLAN_XML)[0], source=plan_source, observed_at="2026-08-25T00:00:00+00:00")
    dialogue = normalize_pcc_row(parse_snapshot_xml(RECRUITMENT_XML)[0], source=dialogue_source, observed_at="2026-08-25T00:00:00+00:00")
    assert plan["source_reference"] == dialogue["source_reference"] == "A-2026-001"
    assert plan["lineage_key"] == dialogue["lineage_key"] == "A-2026-001"
    assert plan["external_id"] != dialogue["external_id"]


def test_signal_store_reingestion_is_idempotent_and_update_is_not_new_signal():
    source = PCCSnapshotSource(6574, "procurement_notice", "PROCUREMENT_PLAN", "https://example.invalid")
    row = parse_snapshot_xml(PLAN_XML)[0]
    first = normalize_pcc_row(row, source=source, observed_at="2026-08-25T00:00:00+00:00")
    updated = dict(first)
    updated["title"] = "道路改善工程（修正版）"
    updated["source_updated_at"] = "2026-08-25T01:00:00+00:00"

    conn = sqlite3.connect(":memory:")
    persist_signal_records(conn, [first], expected_source="TW_PCC")
    persist_signal_records(conn, [first], expected_source="TW_PCC")
    persist_signal_records(conn, [updated], expected_source="TW_PCC")

    count = conn.execute("SELECT COUNT(*) FROM signal_records").fetchone()[0]
    title = conn.execute("SELECT title FROM signal_records").fetchone()[0]
    assert count == 1
    assert title == "道路改善工程（修正版）"


def test_invalid_or_unrecognizable_xml_fails_closed():
    with pytest.raises(RuntimeError, match="invalid XML"):
        parse_snapshot_xml("<root>")
    with pytest.raises(RuntimeError, match="no recognizable procurement rows"):
        parse_snapshot_xml("<root><row><foo>bar</foo></row></root>")


def test_prepared_connector_refuses_missing_live_verified_urls_before_network():
    connector = TaiwanPCCPreparedConnector()
    with pytest.raises(RuntimeError, match="dataset 6574"):
        connector.fetch_snapshot()


def test_production_gate_stays_closed_until_live_contract_is_proven():
    reasons = production_gate_reasons()
    assert "raw_url_unverified:6574,7261" in reasons
    assert "live_payload_contract_unverified" in reasons
    assert "runtime_not_enabled" in reasons
