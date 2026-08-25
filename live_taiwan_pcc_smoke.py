import sqlite3

from signal_store import persist_signal_records
from taiwan_pcc import PCCSnapshotSource, TaiwanPCCPreparedConnector


def main():
    source = PCCSnapshotSource(
        7260,
        "public_viewing_announcement",
        "PROCUREMENT_PLAN",
        "https://web.pcc.gov.tw/tps/tp/OpenData/downloadTpReadOpenDataFile",
    )
    records = TaiwanPCCPreparedConnector(sources=(source,), timeout=45).fetch_snapshot()
    if not records:
        raise SystemExit("official PCC 7260 snapshot returned no normalized records")
    for record in records[:25]:
        assert record["source"] == "TW_PCC"
        assert record["signal_type"] == "PROCUREMENT_PLAN"
        assert record["source_reference"]
        assert record["external_id"] == f"procurement_plan:{record['source_reference']}"
        assert record["lineage_key"] == record["source_reference"]
        assert record["title"] or record["buyer"]

    construction_terms = ("工程", "施工", "建築", "道路", "橋", "隧道", "水利", "整修", "修繕")
    if not any(
        record.get("category_code")
        or any(term in (record.get("title") or "") for term in construction_terms)
        for record in records
    ):
        raise SystemExit("live PCC 7260 payload exposed no construction-relevant classification/title evidence")

    conn = sqlite3.connect(":memory:")
    first_written = persist_signal_records(conn, records, expected_source="TW_PCC")
    persist_signal_records(conn, records, expected_source="TW_PCC")
    count = conn.execute("SELECT COUNT(*) FROM signal_records WHERE source='TW_PCC'").fetchone()[0]
    if count != len({record["external_id"] for record in records}):
        raise SystemExit(f"TW_PCC idempotency mismatch persisted={count} fetched={len(records)}")
    if first_written != len(records):
        raise SystemExit(f"TW_PCC persistence write mismatch written={first_written} fetched={len(records)}")

    print(f"TW_PCC_7260_LIVE_OK records={len(records)} persisted={count} idempotent=1")


if __name__ == "__main__":
    main()
