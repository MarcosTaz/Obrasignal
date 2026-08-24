"""Durable, provenance-first storage for normalized ObraSignal signals.

The legacy ``tenders`` table remains a compatibility projection for actionable
TENDER records.  This module is the canonical durable envelope for staged global
signals, including procurement plans and future forecast/asset/obligation signals.

Only normalized connector output is stored here.  Raw publisher payloads, auth
material and private transport state do not belong in ``normalized_json``.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Mapping


SIGNAL_SCHEMA_VERSION = 1
MAX_NORMALIZED_JSON_BYTES = 512_000

ALLOWED_SIGNAL_TYPES = frozenset(
    {
        "TENDER",
        "PROCUREMENT_PLAN",
        "FORECAST",
        "CAPITAL_PROJECT",
        "MARKET_DIALOGUE",
        "CONTRACT_EXPIRY",
        "AWARD",
        "CONTRACT",
        "BUYER_SIGNAL",
        "COMPETITOR_SIGNAL",
        "ASSET_SIGNAL",
        "OBLIGATION_SIGNAL",
        "SUPPLIER_SIGNAL",
        "RESCUE_SIGNAL",
    }
)


def signal_type_of(record: Mapping | None) -> str:
    """Return the canonical signal type, preserving legacy TENDER compatibility.

    Older connectors predate ``signal_type``.  Missing/blank values therefore map
    to TENDER.  Any *explicit* unknown value fails closed instead of being silently
    reclassified into the tender radar.
    """
    raw = record.get("signal_type") if isinstance(record, Mapping) else None
    if raw is None or not str(raw).strip():
        return "TENDER"
    value = str(raw).strip().upper()
    if value not in ALLOWED_SIGNAL_TYPES:
        raise ValueError(f"unsupported signal_type: {value}")
    return value


def ensure_signal_records(conn) -> None:
    conn.execute(
        '''CREATE TABLE IF NOT EXISTS signal_records (
            source TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            external_id TEXT NOT NULL,
            signal_schema_version INTEGER NOT NULL,
            title TEXT,
            description TEXT,
            buyer TEXT,
            country TEXT,
            value TEXT,
            currency TEXT,
            deadline TEXT,
            target_date TEXT,
            publication_date TEXT,
            published_at TEXT,
            source_updated_at TEXT,
            url TEXT,
            taxonomy TEXT,
            category_code TEXT,
            place TEXT,
            source_reference TEXT,
            normalized_json TEXT NOT NULL,
            first_observed TEXT NOT NULL,
            last_observed TEXT NOT NULL,
            PRIMARY KEY(source, signal_type, external_id)
        )'''
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_signal_records_type_target "
        "ON signal_records(signal_type, target_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_signal_records_source_updated "
        "ON signal_records(source, source_updated_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_signal_records_country_type "
        "ON signal_records(country, signal_type)"
    )


def _canonical_identity(record: Mapping, *, expected_source: str | None = None):
    source = str(record.get("source") or "").strip()
    external_id = str(record.get("external_id") or "").strip()
    if not source:
        raise ValueError("signal source is required")
    if not external_id:
        raise ValueError("signal external_id is required")
    if expected_source is not None and source.upper() != str(expected_source).strip().upper():
        raise ValueError(
            f"staged source mismatch: expected {expected_source!r}, record has {source!r}"
        )
    return source, signal_type_of(record), external_id


def _normalized_snapshot(record: Mapping, *, source: str, signal_type: str, external_id: str) -> str:
    # Connector/runtime-private keys are deliberately excluded.  The snapshot is
    # normalized product data, not a dump of internal control state.
    snapshot = {
        str(key): value
        for key, value in record.items()
        if not str(key).startswith("_")
    }
    snapshot["source"] = source
    snapshot["signal_type"] = signal_type
    snapshot["external_id"] = external_id
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)
    if len(encoded.encode("utf-8")) > MAX_NORMALIZED_JSON_BYTES:
        raise ValueError("normalized signal snapshot exceeds safety limit")
    return encoded


def persist_signal_records(
    conn,
    records,
    *,
    observed_at: str | None = None,
    expected_source: str | None = None,
    commit: bool = True,
) -> int:
    """Validate and idempotently upsert normalized signals.

    When called inside ``source_runtime.commit_staged_source_syncs`` this runs in
    the same transaction as source metadata, lifecycle state and cursor movement.
    A malformed identity/type therefore prevents the cursor from advancing.
    """
    ensure_signal_records(conn)
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    written = 0
    for record in records or []:
        if not isinstance(record, Mapping):
            raise ValueError("signal record must be a mapping")
        source, signal_type, external_id = _canonical_identity(
            record, expected_source=expected_source
        )
        normalized_json = _normalized_snapshot(
            record,
            source=source,
            signal_type=signal_type,
            external_id=external_id,
        )
        conn.execute(
            '''INSERT INTO signal_records(
                source,signal_type,external_id,signal_schema_version,
                title,description,buyer,country,value,currency,deadline,target_date,
                publication_date,published_at,source_updated_at,url,taxonomy,
                category_code,place,source_reference,normalized_json,
                first_observed,last_observed
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source,signal_type,external_id) DO UPDATE SET
                signal_schema_version=excluded.signal_schema_version,
                title=excluded.title,
                description=excluded.description,
                buyer=excluded.buyer,
                country=excluded.country,
                value=excluded.value,
                currency=excluded.currency,
                deadline=excluded.deadline,
                target_date=excluded.target_date,
                publication_date=excluded.publication_date,
                published_at=excluded.published_at,
                source_updated_at=excluded.source_updated_at,
                url=excluded.url,
                taxonomy=excluded.taxonomy,
                category_code=excluded.category_code,
                place=excluded.place,
                source_reference=excluded.source_reference,
                normalized_json=excluded.normalized_json,
                last_observed=excluded.last_observed''',
            (
                source,
                signal_type,
                external_id,
                SIGNAL_SCHEMA_VERSION,
                record.get("title"),
                record.get("description"),
                record.get("buyer"),
                record.get("country"),
                record.get("value"),
                record.get("currency"),
                record.get("deadline"),
                record.get("target_date") or record.get("data_desejada"),
                record.get("publication_date"),
                record.get("published_at"),
                record.get("source_updated_at"),
                record.get("url"),
                record.get("taxonomy"),
                record.get("category_code"),
                record.get("place"),
                record.get("source_reference"),
                normalized_json,
                observed,
                observed,
            ),
        )
        written += 1
    if commit:
        conn.commit()
    return written


def get_signal_record(conn, source: str, external_id: str, signal_type: str = "TENDER"):
    ensure_signal_records(conn)
    canonical_type = signal_type_of({"signal_type": signal_type})
    row = conn.execute(
        "SELECT * FROM signal_records WHERE source=? AND signal_type=? AND external_id=?",
        (str(source).strip(), canonical_type, str(external_id).strip()),
    ).fetchone()
    return dict(row) if row else None
