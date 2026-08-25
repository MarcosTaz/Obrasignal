"""Runtime entry point for the bounded live-validated Taiwan PCC slice.

The slice includes official pre-tender public-viewing signals (7260) and large
procurement suppliers in performance (7264). It does not imply full Taiwan
procurement coverage. Runtime output is conservatively limited to construction /
public-works signals before canonical staging.
"""
from taiwan_pcc import (
    PCCSnapshotSource,
    TaiwanPCCPreparedConnector,
    filter_construction_signals,
)
from incremental_runtime_plugin import install_incremental_source

SOURCE = "TW_PCC"

PCC_PUBLIC_VIEWING_SOURCE = PCCSnapshotSource(
    7260,
    "public_viewing_announcement",
    "PROCUREMENT_PLAN",
    "https://web.pcc.gov.tw/tps/tp/OpenData/downloadTpReadOpenDataFile",
)
PCC_CONTRACT_PERFORMANCE_SOURCE = PCCSnapshotSource(
    7264,
    "large_procurement_suppliers_in_performance",
    "CONTRACT",
    "https://web.pcc.gov.tw/peems/lapeem/lapeemGeneralPolit/downLoadOpenData",
)
LIVE_SOURCES = (PCC_PUBLIC_VIEWING_SOURCE, PCC_CONTRACT_PERFORMANCE_SOURCE)


def fetch_incremental(*, watermark=None, now=None):
    """Fetch and construction-filter the complete current bounded PCC snapshots.

    These official datasets are snapshots rather than a proven publisher delta
    stream. Re-fetch the complete slice, rely on canonical stable identity and
    idempotent upsert, never interpret disappearance as cancellation, and retain
    any existing watermark because no PCC delta cursor has been proven.
    """
    records = TaiwanPCCPreparedConnector(sources=LIVE_SOURCES).fetch_snapshot(observed_at=now)
    construction_records = filter_construction_signals(records)
    if records and not construction_records:
        raise RuntimeError("TW_PCC live snapshot contained records but no defensible construction/public-works signals")
    return construction_records, watermark


def install(app_module, *, source_enabled, record_blocked):
    """Install TW_PCC exactly once through the generic incremental runtime.

    Activation remains caller-controlled/opt-in. This helper does not mutate the
    canonical master queue and does not by itself assert deployment or production.
    """
    return install_incremental_source(
        app_module,
        source=SOURCE,
        fetch_incremental=fetch_incremental,
        source_enabled=source_enabled,
        record_blocked=record_blocked,
    )
