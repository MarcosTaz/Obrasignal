"""Runtime entry point for the bounded Taiwan PCC public-viewing slice.

This runtime intentionally enables only dataset 7260, whose official raw URL has
been live-validated. It does not imply full Taiwan procurement coverage.
"""
from taiwan_pcc import PCCSnapshotSource, TaiwanPCCPreparedConnector
from incremental_runtime_plugin import install_incremental_source

SOURCE = "TW_PCC"

PCC_PUBLIC_VIEWING_SOURCE = PCCSnapshotSource(
    7260,
    "public_viewing_announcement",
    "PROCUREMENT_PLAN",
    "https://web.pcc.gov.tw/tps/tp/OpenData/downloadTpReadOpenDataFile",
)


def fetch_incremental(*, watermark=None, now=None):
    """Return the current official pre-tender snapshot and a conservative cursor.

    PCC 7260 is a rolling one-week snapshot, not a dated append-only feed. The
    caller therefore re-fetches the full official snapshot and relies on canonical
    signal identity/idempotent persistence. No disappearance is interpreted as
    cancellation. The cursor is deliberately preserved because there is no
    publisher delta token proven for this source.
    """
    records = TaiwanPCCPreparedConnector(sources=(PCC_PUBLIC_VIEWING_SOURCE,)).fetch_snapshot(
        observed_at=now
    )
    return records, watermark


def install(app_module, *, source_enabled, record_blocked):
    """Install the live-validated PCC slice exactly once through the generic runtime.

    Activation remains opt-in and must be controlled by the caller's source gate;
    this helper does not mutate the canonical master queue or force production use.
    """
    return install_incremental_source(
        app_module,
        source=SOURCE,
        fetch_incremental=fetch_incremental,
        source_enabled=source_enabled,
        record_blocked=record_blocked,
    )
