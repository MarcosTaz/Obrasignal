"""TEMPORARY forensic probe; remove after measuring full PACC snapshot economics."""
from datetime import datetime, timezone
import json
import time

from dominican_republic_dgcp_pacc import DGCPPACCConfig, DGCPPACCConnector


def test_temporary_dgcp_full_pacc_snapshot_probe():
    now = datetime.now(timezone.utc)
    connector = DGCPPACCConnector(DGCPPACCConfig(page_size=1000, max_pages=60, timeout=45))
    started = time.perf_counter()
    signals = connector.fetch_snapshot(now=now)
    elapsed = round(time.perf_counter() - started, 3)
    summary = {
        "elapsed_seconds": elapsed,
        "signals": len(signals),
        "unique_ids": len({row.get("external_id") for row in signals}),
        "all_works": all(row.get("category_code") == "OBRAS" for row in signals),
        "all_future": all((row.get("target_date") or "") >= now.date().isoformat() for row in signals),
    }
    raise AssertionError("DGCP_PACC_FULL_SNAPSHOT=" + json.dumps(summary, sort_keys=True))
