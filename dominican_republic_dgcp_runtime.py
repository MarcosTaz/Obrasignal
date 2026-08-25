"""Atomic runtime composition for Dominican Republic DGCP under one source identity.

The OCDS transport owns the incremental cursor. PACC is an annual bounded snapshot
without a second cursor. Both transports must complete before the combined source
observation can be staged by ``preload``. This prevents a successful OCDS fetch
from advancing the durable cursor when PACC failed in the same source run.

The canonical Signal projection receives all implemented signal types. The legacy
`tenders` compatibility path receives active TENDER rows only, so plans, awards
and contracts cannot contaminate the old tender projection.
"""
from __future__ import annotations

from dataclasses import dataclass

import dominican_republic_dgcp as _dgcp
import dominican_republic_dgcp_pacc as _pacc


@dataclass(frozen=True)
class DGCPRuntimeObservation:
    legacy_tenders: list
    signals: list
    cursor: str | None


def _assert_source_identity(rows):
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("DO_DGCP runtime received a non-mapping signal")
        if str(row.get("source") or "").strip().upper() != "DO_DGCP":
            raise RuntimeError("DO_DGCP runtime received a signal with foreign source identity")


def _dedupe_signals(rows):
    """Deduplicate by canonical source/type/external identity without losing lifecycle types."""
    deduped = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("DO_DGCP runtime received a non-mapping signal")
        source = str(row.get("source") or "").strip().upper()
        signal_type = str(row.get("signal_type") or "").strip().upper()
        external_id = str(row.get("external_id") or "").strip()
        if not source or not signal_type or not external_id:
            raise RuntimeError("DO_DGCP runtime signal is missing canonical identity")
        key = (source, signal_type, external_id)
        deduped[key] = row
    return list(deduped.values())


def fetch_dgcp_runtime(*, watermark=None, now=None, ocds_fetcher=None, pacc_fetcher=None):
    """Fetch one atomic DGCP observation without committing source state.

    ``ocds_fetcher`` must return ``(signals, cursor)``. ``pacc_fetcher`` returns
    the current annual PROCUREMENT_PLAN snapshot. If either raises, no observation
    is returned and the caller must not stage the cursor.
    """
    fetch_ocds = ocds_fetcher or _dgcp.fetch_dgcp_signals
    fetch_pacc = pacc_fetcher or _pacc.fetch_dgcp_procurement_plans

    ocds_signals, cursor = fetch_ocds(watermark=watermark, now=now)
    pacc_signals = fetch_pacc(now=now)

    ocds_signals = list(ocds_signals or [])
    pacc_signals = list(pacc_signals or [])
    combined = ocds_signals + pacc_signals
    _assert_source_identity(combined)
    combined = _dedupe_signals(combined)

    legacy_tenders = [
        row for row in combined
        if str(row.get("signal_type") or "").strip().upper() == "TENDER"
    ]
    return DGCPRuntimeObservation(
        legacy_tenders=legacy_tenders,
        signals=combined,
        cursor=cursor,
    )
