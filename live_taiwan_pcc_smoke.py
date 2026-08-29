import sqlite3

from signal_store import persist_signal_records
from taiwan_pcc import (
    PCCSnapshotSource,
    TaiwanPCCPreparedConnector,
    filter_construction_signals,
)


def _assert_identity(records, signal_type):
    if not records:
        raise SystemExit(f"official PCC {signal_type} snapshot returned no normalized records")
    prefix = signal_type.lower() + ":"
    for record in records[:25]:
        assert record["source"] == "TW_PCC"
        assert record["signal_type"] == signal_type
        assert record["source_reference"]
        if signal_type == "CONTRACT":
            assert record["vendor_code"]
            assert record["external_id"] == prefix + record["source_reference"] + ":" + record["vendor_code"]
        else:
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
    contract_records = TaiwanPCCPreparedConnector(sources=(contract_source,), timeout=45).fetch_snapshot()
    _assert_identity(contract_records, "CONTRACT")

    raw_records = plan_records + contract_records
    construction_records = filter_construction_signals(raw_records)
    if not construction_records:
        raise SystemExit("live PCC payload exposed no defensible construction/public-works signals")
    if not any(record["signal_type"] == "PROCUREMENT_PLAN" for record in construction_records):
        raise SystemExit("live PCC 7260 produced no construction/public-works pre-tender signal")
    if not any(record["signal_type"] == "CONTRACT" for record in construction_records):
        raise SystemExit("live PCC 7264 produced no construction/public-works contract signal")

    unique = {(record["signal_type"], record["external_id"]) for record in construction_records}
    if len(unique) != len(construction_records):
        raise SystemExit(
            f"TW_PCC construction identity collision fetched={len(construction_records)} unique={len(unique)}"
        )

    conn = sqlite3.connect(":memory:")
    first_written = persist_signal_records(conn, construction_records, expected_source="TW_PCC")
    count_after_first = conn.execute("SELECT COUNT(*) FROM signal_records WHERE source='TW_PCC'").fetchone()[0]
    persist_signal_records(conn, construction_records, expected_source="TW_PCC")
    count_after_second = conn.execute("SELECT COUNT(*) FROM signal_records WHERE source='TW_PCC'").fetchone()[0]

    if first_written != len(construction_records):
        raise SystemExit(
            f"TW_PCC persistence write mismatch written={first_written} fetched={len(construction_records)}"
        )
    if count_after_first != len(construction_records) or count_after_second != len(construction_records):
        raise SystemExit(
            "TW_PCC lossless/idempotency mismatch "
            f"fetched={len(construction_records)} first={count_after_first} second={count_after_second}"
        )

    plan_construction = sum(1 for record in construction_records if record["signal_type"] == "PROCUREMENT_PLAN")
    contract_construction = sum(1 for record in construction_records if record["signal_type"] == "CONTRACT")
    native_basis = sum(1 for record in construction_records if record.get("construction_filter_basis") == "publisher_procurement_nature")
    fallback_basis = sum(1 for record in construction_records if record.get("construction_filter_basis") == "conservative_title_fallback")
    print(
        "TW_PCC_LIVE_OK "
        f"raw_plans={len(plan_records)} raw_contracts={len(contract_records)} "
        f"construction_plans={plan_construction} construction_contracts={contract_construction} "
        f"native_basis={native_basis} fallback_basis={fallback_basis} "
        f"persisted={count_after_second} lossless=1 idempotent=1"
    )


if __name__ == "__main__":
    main()
