"""Atomic runtime composition for Dominican Republic DGCP under one source identity.

The complete process-first DGCP discovery transport owns incremental progress.
PACC is an annual bounded snapshot and does not get a second source cursor.
Instead, this module stores discovery progress and the last successful PACC
snapshot date inside one opaque composite cursor. PACC is due at most once per
Dominican calendar day.

When PACC is due, process/OCDS discovery and PACC must both complete before an
observation is returned; therefore a PACC failure cannot allow a newly discovered
cursor to advance. When PACC has already succeeded that day, only process/OCDS is
fetched.

The canonical Signal projection receives all implemented signal types. The legacy
`tenders` compatibility path receives TENDER rows only, so plans, awards and
contracts cannot contaminate the old tender projection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from zoneinfo import ZoneInfo

import dominican_republic_dgcp_discovery as _discovery
import dominican_republic_dgcp_pacc as _pacc


DGCP_TIMEZONE = ZoneInfo("America/Santo_Domingo")


@dataclass(frozen=True)
class DGCPRuntimeCursor:
    ocds_cursor: str | None = None
    pacc_snapshot_date: str | None = None

    def encode(self):
        return json.dumps(
            {
                "ocds_cursor": self.ocds_cursor,
                "pacc_snapshot_date": self.pacc_snapshot_date,
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def decode(cls, value):
        if not value:
            return cls()
        text = str(value).strip()
        if not text:
            return cls()
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            # Backward compatibility: legacy source state was the raw OCDS cursor.
            return cls(ocds_cursor=text)

        if isinstance(payload, dict) and (
            "ocds_cursor" in payload or "pacc_snapshot_date" in payload
        ):
            ocds = payload.get("ocds_cursor")
            ocds = str(ocds) if ocds not in (None, "") else None
            pacc_date = payload.get("pacc_snapshot_date")
            pacc_date = str(pacc_date).strip() if pacc_date not in (None, "") else None
            if pacc_date:
                try:
                    date.fromisoformat(pacc_date)
                except ValueError:
                    raise RuntimeError("DO_DGCP runtime cursor has invalid pacc_snapshot_date") from None
            return cls(ocds_cursor=ocds, pacc_snapshot_date=pacc_date)

        # An OCDSWindowCursor is itself JSON (e.g. {"completed_through": ...}).
        # Preserve that exact text rather than mistaking it for the composite form.
        return cls(ocds_cursor=text)


@dataclass(frozen=True)
class DGCPRuntimeObservation:
    legacy_tenders: list
    signals: list
    cursor: str | None
    pacc_fetched: bool


def _local_date(now):
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(DGCP_TIMEZONE).date()


def _assert_source_identity(rows):
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("DO_DGCP runtime received a non-mapping signal")
        if str(row.get("source") or "").strip().upper() != "DO_DGCP":
            raise RuntimeError("DO_DGCP runtime received a signal with foreign source identity")


def _dedupe_signals(rows):
    """Deduplicate by canonical source/type/external identity without cross-type loss."""
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
    """Fetch one atomic DGCP observation without committing durable source state."""
    fetch_ocds = ocds_fetcher or _discovery.fetch_dgcp_signals_complete
    fetch_pacc = pacc_fetcher or _pacc.fetch_dgcp_procurement_plans

    state = DGCPRuntimeCursor.decode(watermark)
    local_today = _local_date(now)
    if state.pacc_snapshot_date:
        previous_pacc = date.fromisoformat(state.pacc_snapshot_date)
        if previous_pacc > local_today:
            raise RuntimeError("DO_DGCP runtime cursor contains a future PACC snapshot date")
    pacc_due = state.pacc_snapshot_date != local_today.isoformat()

    ocds_signals, next_ocds_cursor = fetch_ocds(
        watermark=state.ocds_cursor,
        now=now,
    )
    ocds_signals = list(ocds_signals or [])

    if pacc_due:
        # Deliberately fetch after process/OCDS discovery. If this raises, no
        # observation/cursor is returned, so newly discovered progress cannot stage.
        pacc_signals = list(fetch_pacc(now=now) or [])
        next_pacc_date = local_today.isoformat()
    else:
        pacc_signals = []
        next_pacc_date = state.pacc_snapshot_date

    combined = ocds_signals + pacc_signals
    _assert_source_identity(combined)
    combined = _dedupe_signals(combined)

    legacy_tenders = [
        row for row in combined
        if str(row.get("signal_type") or "").strip().upper() == "TENDER"
    ]
    cursor = DGCPRuntimeCursor(
        ocds_cursor=next_ocds_cursor,
        pacc_snapshot_date=next_pacc_date,
    ).encode()
    return DGCPRuntimeObservation(
        legacy_tenders=legacy_tenders,
        signals=combined,
        cursor=cursor,
        pacc_fetched=pacc_due,
    )
