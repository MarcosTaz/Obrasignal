"""Deterministic, low-noise history for canonical opportunity state.

The capability observes normalized Signal records, never raw publisher HTML/XML.
Current Signal state remains authoritative; this module stores compact monitored
snapshots and append-only change sets that explain before -> change -> after.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
import sqlite3
from typing import Any, Mapping

CHANGE_SCHEMA_VERSION = 1
DIFF_POLICY_VERSION = "opportunity-material-diff-v0"
NORMALIZER_VERSION = "canonical-change-normalizer-v0"
MAX_TEXT_CHARS = 20_000
MAX_SNAPSHOT_BYTES = 256_000

MATERIAL = "MATERIAL"
NON_MATERIAL = "NON_MATERIAL"
UNKNOWN = "UNKNOWN"
_MISSING = object()
REVISION_KEYS = (
    "source_version",
    "amendment_number",
    "revision_id",
    "amendment_id",
    "corrigendum_id",
    "native_revision",
    "release_id",
)


@dataclass(frozen=True)
class FieldPolicy:
    name: str
    materiality: str
    kind: str = "text"
    case_insensitive: bool = False
    order_independent: bool = False
    item_identity_keys: tuple[str, ...] = ()


# V0 is intentionally explicit. Retrieval timestamps, hashes and connector-private
# fields are absent by design and therefore cannot become user-visible noise.
FIELD_REGISTRY: dict[str, FieldPolicy] = {
    "deadline": FieldPolicy("deadline", MATERIAL, "date"),
    "value": FieldPolicy("value", MATERIAL, "number"),
    "currency": FieldPolicy("currency", MATERIAL, "text", case_insensitive=True),
    "source_status": FieldPolicy("source_status", MATERIAL, "text", case_insensitive=True),
    "lifecycle_status": FieldPolicy("lifecycle_status", MATERIAL, "text", case_insensitive=True),
    "source_version": FieldPolicy("source_version", MATERIAL, "text"),
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


def _norm_text(value: Any, *, case_insensitive: bool) -> str:
    """Normalize semantics before bounding so large-text hashes remain low-noise."""
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if case_insensitive:
        text = text.casefold()
    if len(text) <= MAX_TEXT_CHARS:
        return text
    digest = sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}:excerpt:{text[:512]}"


def _norm_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        return value.isoformat()
    else:
        text = str(value).strip()
        if not text:
            return ""
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            try:
                return date.fromisoformat(text).isoformat()
            except ValueError:
                pass
        for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return _norm_text(text, case_insensitive=False)
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat()


def _norm_number(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    text = str(value).strip().replace(" ", "")
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        # Do not guess locale separators such as 1.000,00.
        return _norm_text(value, case_insensitive=False)
    normalized = format(number.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _canonical_item(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_item(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_item(item) for item in value]
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


def _native_revision(record: Mapping) -> str | None:
    for key in REVISION_KEYS:
        value = record.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return None


def build_monitored_state(record: Mapping, previous_state: Mapping | None = None) -> dict[str, Any]:
    """Normalize monitored fields while treating absent source keys conservatively.

    Missing key means "not observed in this payload", not "removed". When a
    previous state exists it is carried forward. Explicit null/empty is observable
    and may therefore represent a confirmed removal under connector semantics.
    Publisher-native revision aliases are projected into the monitored
    ``source_version`` field here as well as at the source-runtime boundary so
    direct persistence and reconstructed pre-module baselines retain provenance.
    """
    previous_state = previous_state or {}
    state: dict[str, Any] = {}
    for name, policy in FIELD_REGISTRY.items():
        raw = record.get(name, _MISSING)
        if name == "source_version" and raw is _MISSING:
            revision = _native_revision(record)
            if revision is not None:
                raw = revision
        if raw is _MISSING:
            if name in previous_state:
                state[name] = previous_state[name]
            continue
        state[name] = normalize_field(raw, policy)
    return state


def content_fingerprint(state: Mapping) -> str:
    return sha256(_json(dict(state)).encode("utf-8")).hexdigest()


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
    """Pure deterministic diff over the explicit canonical field registry."""
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
        if new_dt > old_dt:
            return "EXTENDED"
        if new_dt < old_dt:
            return "SHORTENED"
    except (TypeError, ValueError):
        # Mixed offset-aware/naive representations are still a material deadline
        # change, but direction is not asserted when chronology is not comparable.
        return None
    return None


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
        schema_version INTEGER NOT NULL
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_opportunity ON opportunity_snapshots(source, signal_type, external_id, snapshot_id)")
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


def _insert_snapshot(conn, *, source: str, signal_type: str, external_id: str, state: Mapping,
                     observed_at: str, source_updated_at: Any = None, source_version: str | None = None) -> dict[str, Any]:
    encoded = _json(dict(state))
    if len(encoded.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise ValueError("opportunity monitored snapshot exceeds safety limit")
    fingerprint = content_fingerprint(state)
    cursor = conn.execute(
        """INSERT INTO opportunity_snapshots(
           source,signal_type,external_id,source_version,observed_at,source_updated_at,
           canonical_json,content_fingerprint,normalizer_version,schema_version
           ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (
            source, signal_type, external_id, source_version, observed_at,
            source_updated_at, encoded, fingerprint, NORMALIZER_VERSION,
            CHANGE_SCHEMA_VERSION,
        ),
    )
    return {
        "snapshot_id": cursor.lastrowid,
        "canonical_json": encoded,
        "content_fingerprint": fingerprint,
    }


def _bootstrap_from_current_signal(conn, source: str, signal_type: str, external_id: str, observed: str):
    """Use pre-existing current Signal state as first baseline after deployment."""
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='signal_records'"
        ).fetchone()
        if not exists:
            return None
        row = conn.execute(
            """SELECT normalized_json, first_observed, source_updated_at
               FROM signal_records WHERE source=? AND signal_type=? AND external_id=?""",
            (source, signal_type, external_id),
        ).fetchone()
    except sqlite3.DatabaseError:
        return None
    if not row:
        return None
    raw = dict(row) if hasattr(row, "keys") else {
        "normalized_json": row[0], "first_observed": row[1], "source_updated_at": row[2]
    }
    try:
        record = json.loads(raw["normalized_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    state = build_monitored_state(record)
    return _insert_snapshot(
        conn,
        source=source,
        signal_type=signal_type,
        external_id=external_id,
        state=state,
        observed_at=raw.get("first_observed") or observed,
        source_updated_at=raw.get("source_updated_at"),
        source_version=_native_revision(record),
    )


def _change_set_id(source: str, signal_type: str, external_id: str,
                   previous_snapshot_id: int, current_snapshot_id: int,
                   native_revision: str | None) -> str:
    # Snapshot IDs make repeated real transitions A->B->A->B distinct while retry
    # remains idempotent because a committed identical latest state is skipped.
    raw = "|".join((
        source, signal_type, external_id, str(previous_snapshot_id),
        str(current_snapshot_id), native_revision or "",
    ))
    return sha256(raw.encode("utf-8")).hexdigest()


def persist_change_observations(conn, records, *, observed_at: str | None = None,
                                commit: bool = True) -> dict[str, int]:
    """Persist baselines and append-only changes inside the caller transaction."""
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
        if previous is None:
            previous = _bootstrap_from_current_signal(
                conn, source, signal_type, external_id, observed
            )
            if previous is not None:
                snapshots += 1

        previous_state = json.loads(previous["canonical_json"]) if previous else {}
        current_state = build_monitored_state(record, previous_state)
        current_fp = content_fingerprint(current_state)
        if previous and previous["content_fingerprint"] == current_fp:
            continue

        current = _insert_snapshot(
            conn,
            source=source,
            signal_type=signal_type,
            external_id=external_id,
            state=current_state,
            observed_at=observed,
            source_updated_at=record.get("source_updated_at") or record.get("published_at"),
            source_version=_native_revision(record),
        )
        snapshots += 1
        if previous is None:
            continue

        detected = detect_changes(previous_state, current_state)
        if not detected:
            continue
        native_revision = _native_revision(record)
        change_set_id = _change_set_id(
            source, signal_type, external_id,
            previous["snapshot_id"], current["snapshot_id"], native_revision,
        )
        fields = sorted({change["field"] for change in detected})
        aggregate = (
            MATERIAL if any(change["materiality"] == MATERIAL for change in detected)
            else UNKNOWN if any(change["materiality"] == UNKNOWN for change in detected)
            else NON_MATERIAL
        )
        conn.execute(
            """INSERT INTO opportunity_change_sets(
               change_set_id,source,signal_type,external_id,previous_snapshot_id,current_snapshot_id,
               native_revision,source_ref,detected_at,source_updated_at,materiality,
               changed_fields_json,diff_policy_version,schema_version
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                change_set_id, source, signal_type, external_id,
                previous["snapshot_id"], current["snapshot_id"], native_revision,
                _source_ref(record), observed,
                record.get("source_updated_at") or record.get("published_at"),
                aggregate, _json(fields), DIFF_POLICY_VERSION, CHANGE_SCHEMA_VERSION,
            ),
        )
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
                    _json(change["old_value"]), _json(change["new_value"]),
                    change["materiality"], detail,
                ),
            )
            changes_written += 1
    if commit:
        conn.commit()
    return {"snapshots": snapshots, "change_sets": change_sets, "changes": changes_written}


def get_change_history(conn, source: str, external_id: str, signal_type: str = "TENDER",
                       *, material_only: bool = False, limit: int = 50) -> list[dict[str, Any]]:
    ensure_change_history_tables(conn)
    params: list[Any] = [str(source), str(signal_type).upper(), str(external_id)]
    where = "WHERE cs.source=? AND cs.signal_type=? AND cs.external_id=?"
    if material_only:
        where += " AND cs.materiality=?"
        params.append(MATERIAL)
    params.append(max(1, min(200, int(limit))))
    rows = conn.execute(
        f"""SELECT cs.* FROM opportunity_change_sets cs {where}
            ORDER BY cs.detected_at DESC, cs.current_snapshot_id DESC LIMIT ?""",
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
    """Small versioned event contract; delivery belongs to future event plumbing."""
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
