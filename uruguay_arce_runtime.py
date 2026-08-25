"""Atomic runtime composition for Uruguay ARCE tender and PAC signals.

The canonical source identity is ``UY_ARCE`` but it has two different official
transports:

* OCDS RSS/record API: incremental TENDER stream and owner of the durable cursor.
* PAC API: bounded PROCUREMENT_PLAN snapshot with no independent cursor.

This module keeps those transport semantics separate while making one runtime
observation fail closed. Both transports must complete before the caller stages
anything. Only TENDER rows are projected back into the legacy tender pipeline;
all signals are persisted through ``source_runtime`` by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from uruguay_arce import fetch_arce_tenders
from uruguay_arce_pac import fetch_arce_procurement_plans


SOURCE = "UY_ARCE"


@dataclass(frozen=True)
class ARCERuntimeBatch:
    legacy_tenders: tuple[dict, ...]
    signals: tuple[dict, ...]
    cursor: str | None


def _validated(records: Iterable[dict] | None, *, allowed_types: set[str], label: str) -> list[dict]:
    result = []
    for record in records or ():
        if not isinstance(record, dict):
            raise RuntimeError(f"{label} returned a non-mapping record")
        if str(record.get("source") or "").strip().upper() != SOURCE:
            raise RuntimeError(f"{label} returned a record outside {SOURCE}")
        signal_type = str(record.get("signal_type") or "TENDER").strip().upper()
        if signal_type not in allowed_types:
            raise RuntimeError(f"{label} returned unexpected signal_type {signal_type!r}")
        external_id = str(record.get("external_id") or "").strip()
        if not external_id:
            raise RuntimeError(f"{label} returned a record without external_id")
        row = dict(record)
        row["source"] = SOURCE
        row["signal_type"] = signal_type
        result.append(row)
    return result


def _dedupe_signals(records: Iterable[dict]) -> tuple[dict, ...]:
    """Deduplicate only exact canonical signal identities, last observation wins."""
    by_identity: dict[tuple[str, str, str], dict] = {}
    for record in records:
        identity = (
            SOURCE,
            str(record.get("signal_type") or "").strip().upper(),
            str(record.get("external_id") or "").strip(),
        )
        by_identity[identity] = record
    return tuple(by_identity[key] for key in sorted(by_identity))


def fetch_arce_runtime_batch(
    *,
    watermark: str | None = None,
    now=None,
    tender_fetcher: Callable = fetch_arce_tenders,
    plan_fetcher: Callable = fetch_arce_procurement_plans,
) -> ARCERuntimeBatch:
    """Fetch the complete ARCE runtime observation without advancing state.

    The RSS tender fetch executes first because it owns the source cursor. The
    cursor is merely returned, never persisted here. PAC then performs its bounded
    snapshot. If either transport raises or violates the source/type contract,
    this function raises and the caller must not stage the cursor or partial rows.
    """
    tenders, cursor = tender_fetcher(watermark=watermark)
    tender_rows = _validated(tenders, allowed_types={"TENDER"}, label="UY_ARCE RSS")

    plans = plan_fetcher(now=now)
    plan_rows = _validated(plans, allowed_types={"PROCUREMENT_PLAN"}, label="UY_ARCE PAC")

    signals = _dedupe_signals((*tender_rows, *plan_rows))
    return ARCERuntimeBatch(
        legacy_tenders=tuple(tender_rows),
        signals=signals,
        cursor=cursor,
    )
