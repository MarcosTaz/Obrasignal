"""Source-specific metadata sidecar for normalized procurement records.

The legacy ``tenders`` table remains intentionally stable while the global
engine learns source-native taxonomies and lifecycle states. Metadata that is
not safely representable in the legacy schema is persisted here by the same
(source, external_id) identity used by the main opportunity table.
"""
from datetime import datetime, timezone
import json


METADATA_FIELDS = (
    "taxonomy",
    "category_code",
    "source_status",
    "source_phase",
    "signal_type",
    "procurement_method",
    "contract_type",
    "place",
    "source_reference",
    "source_updated_at",
)


def ensure_source_metadata(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS source_record_metadata (
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        taxonomy TEXT,
        category_code TEXT,
        source_status TEXT,
        source_phase TEXT,
        signal_type TEXT,
        procurement_method TEXT,
        contract_type TEXT,
        place TEXT,
        source_reference TEXT,
        source_updated_at TEXT,
        metadata_json TEXT,
        last_observed TEXT NOT NULL,
        PRIMARY KEY(source, external_id)
    )''')


def _extra_metadata(record):
    known = set(METADATA_FIELDS) | {
        "source", "external_id", "title", "description", "buyer", "country",
        "cpv", "value", "deadline", "publication_date", "published_at", "url",
        "market", "score", "priority_label", "priority_class", "match_reason",
    }
    return {key: value for key, value in record.items() if key not in known and value not in (None, "", [], {})}


def persist_source_metadata(conn, records, *, observed_at=None, commit=True):
    ensure_source_metadata(conn)
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    written = 0
    for record in records or []:
        source = str(record.get("source") or "").strip()
        external_id = str(record.get("external_id") or "").strip()
        if not source or not external_id:
            continue
        values = [record.get(field) for field in METADATA_FIELDS]
        extras = _extra_metadata(record)
        conn.execute('''INSERT INTO source_record_metadata(
            source,external_id,taxonomy,category_code,source_status,source_phase,
            signal_type,procurement_method,contract_type,place,source_reference,
            source_updated_at,metadata_json,last_observed
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source,external_id) DO UPDATE SET
            taxonomy=excluded.taxonomy,
            category_code=excluded.category_code,
            source_status=excluded.source_status,
            source_phase=excluded.source_phase,
            signal_type=excluded.signal_type,
            procurement_method=excluded.procurement_method,
            contract_type=excluded.contract_type,
            place=excluded.place,
            source_reference=excluded.source_reference,
            source_updated_at=excluded.source_updated_at,
            metadata_json=excluded.metadata_json,
            last_observed=excluded.last_observed''',
            (source, external_id, *values, json.dumps(extras, ensure_ascii=False, sort_keys=True), observed))
        written += 1
    if commit:
        conn.commit()
    return written


def get_source_metadata(conn, source, external_id):
    ensure_source_metadata(conn)
    row = conn.execute(
        'SELECT * FROM source_record_metadata WHERE source=? AND external_id=?',
        (source, external_id),
    ).fetchone()
    return dict(row) if row else None
