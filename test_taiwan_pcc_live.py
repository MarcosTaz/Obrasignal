import os

import pytest

from taiwan_pcc import (
    PCCSnapshotSource,
    TaiwanPCCPreparedConnector,
    filter_construction_signals,
)

LIVE = os.environ.get("TW_PCC_LIVE") == "1"


@pytest.mark.skipif(not LIVE, reason="set TW_PCC_LIVE=1 for publisher live contract smoke")
def test_pcc_7260_public_viewing_live_contract():
    source = PCCSnapshotSource(
        7260,
        "public_viewing_announcement",
        "PROCUREMENT_PLAN",
        "https://web.pcc.gov.tw/tps/tp/OpenData/downloadTpReadOpenDataFile",
    )
    records = TaiwanPCCPreparedConnector(sources=(source,), timeout=45).fetch_snapshot()
    assert records, "official PCC 7260 snapshot returned no normalized records"
    for record in records[:25]:
        assert record["source"] == "TW_PCC"
        assert record["signal_type"] == "PROCUREMENT_PLAN"
        assert record["source_reference"]
        assert record["external_id"] == f"procurement_plan:{record['source_reference']}"
        assert record["lineage_key"] == record["source_reference"]
        assert record["title"] or record["buyer"]

    construction_records = filter_construction_signals(records)
    assert construction_records, "live PCC 7260 payload exposed no defensible construction/public-works signals"
    assert all(record.get("construction_filter_basis") for record in construction_records)
