"""Deterministic, low-noise history for canonical opportunity state.

This capability observes normalized Signal records. It never diffs raw publisher
HTML/XML and does not deliver notifications. The current Signal remains the source
of truth; this module preserves compact monitored snapshots plus append-only
change sets so a user can answer "what changed?" without rereading the source.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any, Mapping


CHANGE_SCHEMA_VERSION = 1
DIFF_POLICY_VERSION = "opportunity-material-diff-v0"
NORMALIZER_VERSION = "canonical-change-normalizer-v0"
MAX_TEXT_CHARS = 20_000

MATERIAL = "MATERIAL"
NON_MATERIAL = "NON_MATERIAL"
UNKNOWN = "UNKNOWN"

_MISSING = object()


@dataclass(frozen=True)
class FieldPolicy:
    name: str
    materiality: str
    kind: str = "text"
    case_insensitive: bool = False
    order_independent: bool = False
    item_identity_keys: tuple[str, ...] = ()


# Central v0 registry. Only normalized, product-meaningful fields are monitored.
FIELD_REGISTRY: dict[str, FieldPolicy] = {
    "deadline": FieldPolicy("deadline", MATERIAL, "date"),
    "value": FieldPolicy("value", MATERIAL, "number"),
    "currency": FieldPolicy("currency", MATERIAL, "text", case_insensitive=True),
    "source_status": FieldPolicy("source_status", MATERIAL, "text", case_insensitive=True),
    "lifecycle_status": FieldPolicy("lifecycle_status", MATERIAL, "text", case_insensitive=True),
    "title": FieldPolicy("title", MATERIAL, "text", case_insensitive=True),
    "description": FieldPolicy("description", MATERIAL, "text"),
    "buyer": FieldPolicy("buyer", MATERIAL, "text", case_insensitive=True),
    "place": FieldPolicy("place", MATERIAL, "text", case_insensitive=True),
    "lots": FieldPolicy(
        "lots", MATERIAL, "collection", order_independent=True,
        item_identity_keys=("id", "lot_id", "identifier", "title"),
    ),
    "documents": FieldPolicy(
        "documents", MATERIAL, "collection", order_independent=True,
        item_identity_keys=("id", "document_id", "url", "name", "title"),
    ),
    "requirements": FieldPolicy(
        "requirements", MATERIAL, "collection", order_independent=True,
        item_identity_keys=("id", "requirement_id", "code", "name", "title"),
    ),
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _bounded_text(value: Any) -> str:
    text = str(value or "")
    if len(text) > MAX_TEXT_CHARS:
        # Large prose is represented by a stable digest plus a bounded excerpt.
        digest = sha256(text.encode("utf-8")).hexdigest()
        return f"sha256:{digest}:excerpt:{text[:512]}"
    return text


def _norm_text(value: Any, *, case_insensitive: bool) -> str:
    text = re.sub(r"\s+", " ", _bounded_text(value).strip())
    return text.casefold() if case_insensitive else text


def _norm_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return _norm_text(text, case_insensitive=False)


def _norm_number(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    text = str(value).strip().replace(" ", "")
    # Canonical connectors should already expose numeric values. We normalize
    # safe decimal representations only and never guess locale separators.
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return _norm_text(value, case_insensitive=False)
    normalized = format(number.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _canonical_item(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical_item(v) for k, v in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, list):
        return [_canonical_item(v) for v in value]
    if isinstance(value, tuple):
        return [_canonical_item(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.strip())
    return value


def _norm_collection(value: Any, policy: FieldPolicy) -> list[Any]:
    if value in (None, ""):
        return []
    values = list(value) if isinstance(value, (list, tuple, set)) else [value]
    normalized = [_canonical_item(item) for item in values]
    if policy.order_independent:
        normalized.sort(key=_json)
    return normalized


def normalize_field(value: Any, policy: FieldPolicy) -> Any:
    if policy.kind == "date":
        return _norm_date(value)
    if policy.kind == "number":
        return _norm_number(value)
    if policy.kind == "collection":
        return _norm_collection(value, policy)
    return _norm_text(value, case_insensitive=policy.case_insensitive)


def _raw_display(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_TEXT_CHARS:
        return {"digest": sha256(value.encode("utf-8")).hexdigest(), "excerpt": value[:512], "truncated": True}
    return value


def build_monitored_state(record: Mapping, previous_state: Mapping | None = None) -> dict[str, Any]:
    """Build canonical monitored state, carrying forward temporarily missing keys.

    A key absent from a source observation is not treated as a confirmed removal.
    An explicitly supplied null/empty value remains observable and can therefore
    represent a real removal when the connector's canonical contract says so.
    """
    previous_state = previous_state or {}
    state: dict[str, Any] = {}
    for name, policy in FIELD_REGISTRY.items():
        raw = record.get(name, _MISSING)
        if raw is _MISSING:
            if name in previous_state:
                state[name] = previous_state[name]
            continue
        state[name] = normalize_field(raw, policy)
    return state


def content_fingerprint(state: Mapping) -> str:
    return sha256(_json(dict(state)).encode("utf-8")).hexdigest()


def _native_revision(record: Mapping) -> str | None:
    for key in (
        "source_version", "revision_id", "amendment_id", "corrigendum_id",
        "native_revision", "release_id",
    ):
        value = record.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return None


def _source_ref(record: Mapping) -> str | None:
    for key in ("evidence_ref", "source_ref", "source_reference", "url"):
        value = record.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return None


def _collection_identity(item: Any, policy: FieldPolicy) -> str | None:
    if not isinstance(item, Mapping):
        return _json(item)
    for key in policy.item_identity_keys:
        value = item.get(key)
        if value not in (None, ""):
            return f"{key}:{_norm_text(value, case_insensitive=True)}"
    return None


def _collection_changes(field: str, old: list[Any], new: list[Any], policy: FieldPolicy) -> list[dict[str, Any]]:
    old_map: dict[str, Any] = {}
    new_map: dict[str, Any] = {}
    for item in old:
        identity = _collection_identity(item, policy)
        if identity is None or identity in old_map:
            return [{"field": field, "change_type": "CHANGED", "old_value": old, "new_value": new}]
        old_map[identity] = item
    for item in new:
        identity = _collection_identity(item, policy)
        if identity is None or identity in new_map:
            return [{"field": field, "change_type": "CHANGED", "old_value": old, "new_value": new}]
        new_map[identity] = item
    changes: list[dict[str, Any]] = []
    for identity in sorted(old_map.keys() - new_map.keys()):
        changes.append({"field": field, "change_type": "ITEM_REMOVED", "old_value": old_map[identity], "new_value": None})
    for identity in sorted(new_map.keys() - old_map.keys()):
        changes.append({"field": field, "change_type": "ITEM_ADDED", "old_value": None, "new_value": new_map[identity]})
    for identity in sorted(old_map.keys() & new_map.keys()):
        if old_map[identity] != new_map[identity]:
            changes.append({"field": field, "change_type": "CHANGED", "old_value": old_map[identity], "new_value": new_map[identity]})
    return changes


def detect_changes(previous_state: Mapping, current_state: Mapping) -> list[dict[str, Any]]:
    """Pure deterministic diff over the monitored canonical field registry."""
    changes: list[dict[str, Any]] = []
    for field, policy in FIELD_REGISTRY.items():
        old = previous_state.get(field, _MISSING)
        new = current_state.get(field, _MISSING)
        if old is _MISSING and new is _MISSING:
            continue
        if old is _MISSING:
            changes.append({"field": field, "change_type": "ADDED", "old_value": None, "new_value": new, "materiality": policy.materiality})
            continue
        if new is _MISSING:
            # build_monitored_state normally carries forward a missing field.
            # Keep the pure engine conservative if called directly.
            changes.append({"field": field, "change_type": "UNKNOWN_CHANGE", "old_value": old, "new_value": None, "materiality": UNKNOWN})
            continue
        if old == new:
            continue
        if policy.kind == "collection":
            field_changes = _collection_changes(field, list(old), list(new), policy)
            for change in field_changes:
                change["materiality"] = policy.materiality
            changes.extend(field_changes)
        else:
            changes.append({"field": field, "change_type": "CHANGED", "old_value": old, "new_value": new, "materiality": policy.materiality})
    return changes


def _deadline_direction(old: Any, new: Any) -> str | None:
    try:
        old_dt = datetime.fromisoformat(str(old).replace("Z", "+00:00"))
        new_dt = datetime.fromisoformat(str(new).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        try:
            old_dt = datetime.fromisoformat(str(old)[:10])
            new_dt = datetime.fromisoformat(str(new)[:10])
        except (TypeError, ValueError):
            return None
    if new_dt > old_dt:
        return "EXTENDED"
    if new_dt < old_dt:
        return "SHORTENED"
    return None


def _change_set_id(source: str, signal_type: str, external_id: str, old_fp: str, new_fp: str, native_revision: str | None) -> str:
    raw = "|".join((source, signal_type, external_id, old_fp, new_fp, native_revision or ""))
    return sha256(raw.encode("utf-8")).hexdigest()


def ensure_change_history_tables(conn) -> None:
    conn.execute('''CREATE TABLE IF NOT EXISTS opportunity_snapshots (
        snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        signal_type TEXT NOT NULL,
        external_id TEXT NOT NULL,
        source_version TEXT,
        observed_at TEXT NOT NULL,
        source_updated_at TEXT,
        canonical_json TEXT NOT NULL,
        content_fingerprint TEXT NOT NULL,
        normalizer_version TEXT NOT NULL,
        schema_version INTEGER NOT NULL,
        UNIQUE(source, signal_type, external_id, content_fingerprint)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS opportunity_change_sets (
        change_set_id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        signal_type TEXT NOT NULL,
        external_id TEXT NOT NULL,
        previous_snapshot_id INTEGER NOT NULL,
        current_snapshot_id INTEGER NOT NULL,
        native_revision TEXT,
        source_ref TEXT,
        detected_at TEXT NOT NULL,
        source_updated_at TEXT,
        materiality TEXT NOT NULL,
        changed_fields_json TEXT NOT NULL,
        diff_policy_version TEXT NOT NULL,
        schema_version INTEGER NOT NULL,
        FOREIGN KEY(previous_snapshot_id) REFERENCES opportunity_snapshots(snapshot_id),
        FOREIGN KEY(current_snapshot_id) REFERENCES opportunity_snapshots(snapshot_id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS opportunity_changes (
        change_id INTEGER PRIMARY KEY AUTOINCREMENT,
        change_set_id TEXT NOT NULL,
        field TEXT NOT NULL,
        change_type TEXT NOT NULL,
        old_value_json TEXT,
        new_value_json TEXT,
        materiality TEXT NOT NULL,
        detail TEXT,
        FOREIGN KEY(change_set_id) REFERENCES opportunity_change_sets(change_set_id)
    )''')
    conn.execute("CREATE INDEX IF NOT EXISTS idx_change_sets_opportunity ON opportunity_change_sets(source, signal_type, external_id, detected_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_changes_set ON opportunity_changes(change_set_id)")


def _latest_snapshot(conn, source: str, signal_type: str, external_id: str):
    row = conn.execute(
        """SELECT * FROM opportunity_snapshots
           WHERE source=? AND signal_type=? AND external_id=?
           ORDER BY snapshot_id DESC LIMIT 1""",
        (source, signal_type, external_id),
    ).fetchone()
    return dict(row) if row else None


def _identity(record: Mapping) -> tuple[str, str, str]:
    source = str(record.get("source") or "").strip()
    signal_type = str(record.get("signal_type") or "TENDER").strip().upper()
    external_id = str(record.get("external_id") or "").strip()
    if not source or not external_id:
        raise ValueError("change history requires source and external_id")
    return source, signal_type, external_id


def persist_change_observations(conn, records, *, observed_at: str | None = None, commit: bool = True) -> dict[str, int]:
    """Persist baselines/change sets idempotently inside the caller transaction."""
    ensure_change_history_tables(conn)
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    snapshots = 0
    change_sets = 0
    changes_written = 0
    for record in records or []:
        if not isinstance(record, Mapping):
            raise ValueError("change history record must be a mapping")
        source, signal_type, external_id = _identity(record)
        previous = _latest_snapshot(conn, source, signal_type, external_id)
        previous_state = json.loads(previous["canonical_json"]) if previous else {}
        current_state = build_monitored_state(record, previous_state)
        current_fp = content_fingerprint(current_state)
        if previous and previous["content_fingerprint"] == current_fp:
            continue

        cursor = conn.execute(
            """INSERT OR IGNORE INTO opportunity_snapshots(
               source,signal_type,external_id,source_version,observed_at,source_updated_at,
               canonical_json,content_fingerprint,normalizer_version,schema_version
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                source, signal_type, external_id, _native_revision(record), observed,
                record.get("source_updated_at") or record.get("published_at"),
                _json(current_state), current_fp, NORMALIZER_VERSION, CHANGE_SCHEMA_VERSION,
            ),
        )
        if cursor.rowcount:
            snapshots += 1
        current = _latest_snapshot(conn, source, signal_type, external_id)
        if previous is None:
            continue

        detected = detect_changes(previous_state, current_state)
        if not detected:
            continue
        old_fp = previous["content_fingerprint"]
        native_revision = _native_revision(record)
        change_set_id = _change_set_id(source, signal_type, external_id, old_fp, current_fp, native_revision)
        fields = sorted({change["field"] for change in detected})
        aggregate_materiality = MATERIAL if any(c["materiality"] == MATERIAL for c in detected) else UNKNOWN if any(c["materiality"] == UNKNOWN for c in detected) else NON_MATERIAL
        inserted = conn.execute(
            """INSERT OR IGNORE INTO opportunity_change_sets(
               change_set_id,source,signal_type,external_id,previous_snapshot_id,current_snapshot_id,
               native_revision,source_ref,detected_at,source_updated_at,materiality,
               changed_fields_json,diff_policy_version,schema_version
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                change_set_id, source, signal_type, external_id,
                previous["snapshot_id"], current["snapshot_id"], native_revision,
                _source_ref(record), observed,
                record.get("source_updated_at") or record.get("published_at"),
                aggregate_materiality, _json(fields), DIFF_POLICY_VERSION, CHANGE_SCHEMA_VERSION,
            ),
        )
        if not inserted.rowcount:
            continue
        change_sets += 1
        for change in detected:
            detail = None
            if change["field"] == "deadline" and change["change_type"] == "CHANGED":
                detail = _deadline_direction(change["old_value"], change["new_value"])
            conn.execute(
                """INSERT INTO opportunity_changes(
                   change_set_id,field,change_type,old_value_json,new_value_json,materiality,detail
                   ) VALUES(?,?,?,?,?,?,?)""",
                (
                    change_set_id, change["field"], change["change_type"],
                    _json(_raw_display(change["old_value"])),
                    _json(_raw_display(change["new_value"])),
                    change["materiality"], detail,
                ),
            )
            changes_written += 1
    if commit:
        conn.commit()
    return {"snapshots": snapshots, "change_sets": change_sets, "changes": changes_written}


def get_change_history(conn, source: str, external_id: str, signal_type: str = "TENDER", *, material_only: bool = False, limit: int = 50) -> list[dict[str, Any]]:
    ensure_change_history_tables(conn)
    params: list[Any] = [source, signal_type.upper(), external_id]
    where = "WHERE cs.source=? AND cs.signal_type=? AND cs.external_id=?"
    if material_only:
        where += " AND cs.materiality=?"
        params.append(MATERIAL)
    params.append(max(1, min(200, int(limit))))
    rows = conn.execute(
        f"""SELECT cs.* FROM opportunity_change_sets cs
            {where} ORDER BY cs.detected_at DESC, cs.change_set_id DESC LIMIT ?""",
        params,
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        change_rows = conn.execute(
            """SELECT field,change_type,old_value_json,new_value_json,materiality,detail
               FROM opportunity_changes WHERE change_set_id=? ORDER BY change_id""",
            (item["change_set_id"],),
        ).fetchall()
        item["changed_fields"] = json.loads(item.pop("changed_fields_json"))
        item["changes"] = [
            {
                "field": change["field"],
                "change_type": change["change_type"],
                "old_value": json.loads(change["old_value_json"]) if change["old_value_json"] is not None else None,
                "new_value": json.loads(change["new_value_json"]) if change["new_value_json"] is not None else None,
                "materiality": change["materiality"],
                "detail": change["detail"],
            }
            for change in change_rows
        ]
        result.append(item)
    return result


def opportunity_changed_event(change_set: Mapping) -> dict[str, Any]:
    """Small versioned event payload for future generic event infrastructure."""
    return {
        "event_type": "opportunity.changed",
        "event_version": 1,
        "opportunity_id": {
            "source": change_set.get("source"),
            "signal_type": change_set.get("signal_type"),
            "external_id": change_set.get("external_id"),
        },
        "change_set_id": change_set.get("change_set_id"),
        "changed_fields": list(change_set.get("changed_fields") or []),
        "materiality": change_set.get("materiality") or UNKNOWN,
    }
