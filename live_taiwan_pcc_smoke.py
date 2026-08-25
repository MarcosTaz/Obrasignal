import sqlite3

from signal_store import persist_signal_records
from taiwan_pcc import PCCSnapshotSource, TaiwanPCCPreparedConnector


def _assert_identity(records, signal_type):
    if not records:
        raise SystemExit(f"official PCC {signal_type} snapshot returned no normalized records")
    prefix = signal_type.lower() + ":"
    for record in records[:25]:
        assert record["source"] == "TW_PCC"
        assert record["signal_type"] == signal_type
        assert record["source_reference"]
        assert record["external_id"] == prefix + record["source_reference"]
        assert record["lineage_key"] == record["source_reference"]
        assert record["title"] or record["buyer"]


def main():
    plan_source = PCCSnapshotSource(
        7260,
        "public_viewing_announcement",
        "PROCUREMENT_PLAN",
        "https://web.pcc.gov.tw/tps/tp/OpenData/downloadTpReadOpenDataFile",
    )
    contract_source = PCCSnapshotSource(
        7264,
        "large_procurement_suppliers_in_performance",
        "CONTRACT",
        "https://web.pcc.gov.tw/peems/lapeem/lapeemGeneralPolit/downLoadOpenData",
    )

    plan_records = TaiwanPCCPreparedConnector(sources=(plan_source,), timeout=45).fetch_snapshot()
    _assert_identity(plan_records, "PROCUREMENT_PLAN")

    construction_terms = ("工程", "施工", "建築", "道路", "橋", "隧道", "水利", "整修", "修繕")
    if not any(
        record.get("category_code")
        or any(term in (record.get("title") or "") for term in construction_terms)
        for record in plan_records
    ):
        raise SystemExit("live PCC 7260 payload exposed no construction-relevant classification/title evidence")

    contract_records = TaiwanPCCPreparedConnector(sources=(contract_source,), timeout=45).fetch_snapshot()
    _assert_identity(contract_records, "CONTRACT")
    if not any(record.get("vendor_name") or record.get("value") for record in contract_records):
        raise SystemExit("live PCC 7264 payload exposed no supplier/value contract evidence")

    records = plan_records + contract_records
    conn = sqlite3.connect(":memory:")
    first_written = persist_signal_records(conn, records, expected_source="TW_PCC")
    persist_signal_records(conn, records, expected_source="TW_PCC")
    count = conn.execute("SELECT COUNT(*) FROM signal_records WHERE source='TW_PCC'").fetchone()[0]
    unique = len({(record["signal_type"], record["external_id"]) for record in records})
    if count != unique:
        raise SystemExit(f"TW_PCC idempotency mismatch persisted={count} unique={unique}")
    if first_written != len(records):
        raise SystemExit(f"TW_PCC persistence write mismatch written={first_written} fetched={len(records)}")

    print(
        "TW_PCC_LIVE_OK "
        f"plans={len(plan_records)} contracts={len(contract_records)} "
        f"persisted={count} idempotent=1"
    )


if __name__ == "__main__":
    main()
