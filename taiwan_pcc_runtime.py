"""Runtime entry point for the bounded Taiwan PCC public-viewing slice.

This runtime intentionally enables only dataset 7260, whose official raw URL is
known. It does not imply full Taiwan procurement coverage.
"""
from taiwan_pcc import PCCSnapshotSource, TaiwanPCCPreparedConnector

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
    cancellation. The cursor is deliberately unchanged/None because there is no
    publisher delta token proven for this source.
    """
    records = TaiwanPCCPreparedConnector(sources=(PCC_PUBLIC_VIEWING_SOURCE,)).fetch_snapshot(
        observed_at=now
    )
    return records, watermark
