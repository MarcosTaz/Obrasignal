import sqlite3

import pytest

from signal_store import persist_signal_records
from taiwan_pcc import (
    PCCSnapshotSource,
    TaiwanPCCPreparedConnector,
    construction_basis,
    filter_construction_signals,
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

CONTRACT_XML = """<root>
<row><標案案號>A-2026-001</標案案號><標案名稱>道路改善工程</標案名稱><機關名稱>測試市政府</機關名稱><廠商代碼>V001</廠商代碼><廠商名稱>甲公司</廠商名稱><得標金額>1000000</得標金額></row>
<row><標案案號>A-2026-001</標案案號><標案名稱>道路改善工程</標案名稱><機關名稱>測試市政府</機關名稱><廠商代碼>V002</廠商代碼><廠商名稱>乙公司</廠商名稱><得標金額>500000</得標金額></row>
</root>"""


class FakeResponse:
    def __init__(self, content, *, error=None):
        self.content = content
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        return self.response


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
    assert record["target_date"] == "2026-09-01"
    assert record["source_updated_at"] is None


def test_lineage_key_survives_signal_stage_change_without_identity_collision():
    plan_source = PCCSnapshotSource(6574, "procurement_notice", "PROCUREMENT_PLAN", "https://example.invalid")
    dialogue_source = PCCSnapshotSource(7261, "public_recruitment_announcement", "MARKET_DIALOGUE", "https://example.invalid")
    plan = normalize_pcc_row(parse_snapshot_xml(PLAN_XML)[0], source=plan_source, observed_at="2026-08-25T00:00:00+00:00")
    dialogue = normalize_pcc_row(parse_snapshot_xml(RECRUITMENT_XML)[0], source=dialogue_source, observed_at="2026-08-25T00:00:00+00:00")
    assert plan["source_reference"] == dialogue["source_reference"] == "A-2026-001"
    assert plan["lineage_key"] == dialogue["lineage_key"] == "A-2026-001"
    assert plan["external_id"] != dialogue["external_id"]


def test_contract_identity_preserves_multiple_native_vendors_per_case():
    source = PCCSnapshotSource(7264, "large_procurement_suppliers_in_performance", "CONTRACT", "https://example.invalid")
    rows = parse_snapshot_xml(CONTRACT_XML)
    records = [normalize_pcc_row(row, source=source) for row in rows]
    assert [record["external_id"] for record in records] == [
        "contract:A-2026-001:V001",
        "contract:A-2026-001:V002",
    ]
    assert {record["lineage_key"] for record in records} == {"A-2026-001"}
    assert {record["vendor_code"] for record in records} == {"V001", "V002"}


def test_contract_without_native_vendor_code_is_rejected():
    source = PCCSnapshotSource(7264, "large_procurement_suppliers_in_performance", "CONTRACT", "https://example.invalid")
    row = {"tendernumber": "A-2026-001", "vendorname": "甲公司"}
    assert normalize_pcc_row(row, source=source) is None


def test_missing_native_case_number_is_rejected_instead_of_synthesized():
    source = PCCSnapshotSource(6574, "procurement_notice", "PROCUREMENT_PLAN", "https://example.invalid")
    row = {"tendername": "道路改善工程", "organizationname": "測試市政府"}
    assert normalize_pcc_row(row, source=source) is None


def test_construction_filter_prefers_publisher_native_procurement_nature():
    record = {"title": "一般採購", "category_code": "公共工程"}
    assert construction_basis(record) == "publisher_procurement_nature"
    assert filter_construction_signals([record])[0]["construction_filter_basis"] == "publisher_procurement_nature"


def test_non_construction_native_category_does_not_fall_through_to_title_keyword():
    record = {"title": "道路改善工程", "category_code": "財物採購"}
    assert construction_basis(record) is None
    assert filter_construction_signals([record]) == []


def test_conservative_title_fallback_excludes_adjacent_service_false_positive():
    true_work = {"title": "道路改善工程", "category_code": ""}
    false_positive = {"title": "道路工程顧問服務", "category_code": ""}
    software = {"title": "道路資訊系統維護", "category_code": ""}
    assert construction_basis(true_work) == "conservative_title_fallback"
    assert construction_basis(false_positive) is None
    assert construction_basis(software) is None


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


def test_transport_uses_bounded_timeout_and_normalizes_complete_snapshot():
    source = PCCSnapshotSource(6574, "procurement_notice", "PROCUREMENT_PLAN", "https://example.invalid")
    session = FakeSession(FakeResponse(PLAN_XML.encode("utf-8")))
    connector = TaiwanPCCPreparedConnector(sources=(source,), session=session, timeout=12)
    records = connector.fetch_snapshot(observed_at="2026-08-25T00:00:00+00:00")
    assert session.calls == [("https://example.invalid", 12)]
    assert len(records) == 1
    assert records[0]["external_id"] == "procurement_plan:A-2026-001"


def test_transport_http_error_propagates_and_never_becomes_zero_results():
    source = PCCSnapshotSource(6574, "procurement_notice", "PROCUREMENT_PLAN", "https://example.invalid")
    session = FakeSession(FakeResponse(b"", error=RuntimeError("503 upstream")))
    connector = TaiwanPCCPreparedConnector(sources=(source,), session=session)
    with pytest.raises(RuntimeError, match="503 upstream"):
        connector.fetch_snapshot()


def test_empty_success_payload_fails_closed_instead_of_advancing_as_zero():
    source = PCCSnapshotSource(6574, "procurement_notice", "PROCUREMENT_PLAN", "https://example.invalid")
    connector = TaiwanPCCPreparedConnector(sources=(source,), session=FakeSession(FakeResponse(b"")))
    with pytest.raises(RuntimeError, match="snapshot was empty"):
        connector.fetch_snapshot()


def test_full_source_set_remains_gated_but_live_slice_no_longer_requires_payload_proof():
    reasons = production_gate_reasons()
    assert "raw_url_unverified:6574,7261" in reasons
    assert "runtime_not_integrated" in reasons
    assert all("live_payload_contract" not in reason for reason in reasons)
