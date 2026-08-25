"""Conservative procurement lifecycle lineage for canonical ObraSignal signals.

Lineage answers which canonical procurement events belong to the same lifecycle.
It is deliberately narrower than entity resolution: source-native relations and
strong procurement identifiers may confirm lineage; title, buyer, value, place or
timing alone never do.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Iterable, Mapping, Sequence

from signal_store import signal_type_of

LINEAGE_RULE_VERSION = "lineage-v0.2"
LINEAGE_SCHEMA_VERSION = 1

NODE_TYPES = frozenset({
    "PROCUREMENT_PLAN", "MARKET_DIALOGUE", "TENDER", "AMENDMENT",
    "CORRIGENDUM", "AWARD", "CONTRACT",
})
RELATIONSHIP_TYPES = frozenset({
    "PRECEDES", "DERIVED_FROM", "AMENDS", "CORRECTS", "SUPERSEDES",
    "RESULTED_IN", "CONTRACTED_AS", "RELATED_TO",
})
BASIS_TYPES = frozenset({"EXPLICIT", "DETERMINISTIC", "INFERRED", "UNKNOWN"})
CONFIDENCE_TYPES = frozenset({"HIGH", "MEDIUM", "LOW", "UNKNOWN"})
DAG_RELATIONSHIP_TYPES = frozenset({
    "PRECEDES", "DERIVED_FROM", "AMENDS", "CORRECTS", "SUPERSEDES",
    "RESULTED_IN", "CONTRACTED_AS",
})

_STAGE_ORDER = {
    "PROCUREMENT_PLAN": 10,
    "MARKET_DIALOGUE": 20,
    "TENDER": 30,
    "AMENDMENT": 35,
    "CORRIGENDUM": 35,
    "AWARD": 40,
    "CONTRACT": 50,
}
_SUBJECT_TO_TARGET_RELATIONS = frozenset({
    "DERIVED_FROM", "AMENDS", "CORRECTS", "SUPERSEDES",
})
_MAX_IDENTIFIER = 512
_MAX_REASON = 2048


@dataclass(frozen=True)
class LineageEdge:
    edge_id: str
    from_entity_type: str
    from_entity_id: str
    to_entity_type: str
    to_entity_id: str
    relationship_type: str
    confidence: str
    basis: str
    reasons: tuple[str, ...]
    source_ref: str | None = None
    native_relation_type: str | None = None
    rule_version: str = LINEAGE_RULE_VERSION
    lot_id: str | None = None

    def as_dict(self):
        return {
            "edge_id": self.edge_id,
            "from_entity_type": self.from_entity_type,
            "from_entity_id": self.from_entity_id,
            "to_entity_type": self.to_entity_type,
            "to_entity_id": self.to_entity_id,
            "relationship_type": self.relationship_type,
            "confidence": self.confidence,
            "basis": self.basis,
            "reasons": list(self.reasons),
            "source_ref": self.source_ref,
            "native_relation_type": self.native_relation_type,
            "rule_version": self.rule_version,
            "lot_id": self.lot_id,
        }


@dataclass(frozen=True)
class LineageCandidate:
    from_entity_id: str
    to_entity_id: str
    signals: tuple[str, ...]
    strength: str
    status: str = "UNRESOLVED"

    def as_dict(self):
        return {
            "from_entity_id": self.from_entity_id,
            "to_entity_id": self.to_entity_id,
            "signals": list(self.signals),
            "strength": self.strength,
            "status": self.status,
        }


def _text(value, *, limit=_MAX_IDENTIFIER):
    text = "" if value is None else str(value).strip()
    if len(text) > limit:
        raise ValueError("lineage identifier exceeds safety limit")
    return text


def _node_type(record: Mapping):
    explicit = _text(record.get("lineage_node_type") or "").upper()
    if explicit:
        if explicit not in NODE_TYPES:
            raise ValueError(f"unsupported lineage node type: {explicit}")
        return explicit
    signal_type = signal_type_of(record)
    return signal_type if signal_type in NODE_TYPES else None


def _entity_id(record: Mapping):
    source = _text(record.get("source"))
    external_id = _text(record.get("external_id"))
    if not source or not external_id:
        raise ValueError("lineage record requires source and external_id")
    return f"{source}:{external_id}"


def _lot_id(record: Mapping):
    return _text(record.get("lot_id") or record.get("technical_lot_id") or "") or None


def _date_value(record: Mapping):
    for key in (
        "effective_at", "occurred_at", "published_at", "source_updated_at",
        "publication_date", "target_date",
    ):
        value = _text(record.get(key) or "", limit=128)
        if value:
            return value
    return None


def _record_snapshot(record: Mapping):
    return {
        "entity_id": _entity_id(record),
        "entity_type": _node_type(record),
        "source": _text(record.get("source")),
        "external_id": _text(record.get("external_id")),
        "title": _text(record.get("title") or "", limit=2000),
        "buyer": _text(record.get("buyer") or "", limit=2000),
        "buyer_id": _text(record.get("buyer_id") or record.get("buyer_identifier") or ""),
        "country": _text(record.get("country") or "", limit=128),
        "jurisdiction": _text(record.get("jurisdiction") or record.get("country") or "", limit=128),
        "ocid": _text(record.get("ocid") or ""),
        "procurement_reference": _text(
            record.get("procurement_reference")
            or record.get("procedure_id")
            or record.get("procurement_id")
            or ""
        ),
        "source_reference": _text(record.get("source_reference") or ""),
        "lot_id": _lot_id(record),
        "event_date": _date_value(record),
        "is_actionable": record.get("is_actionable"),
    }


def _edge_id(from_id, to_id, relationship_type, basis, source_ref,
             native_relation_type, rule_version, lot_id):
    raw = "\x1f".join(str(value or "") for value in (
        from_id, to_id, relationship_type, basis, source_ref,
        native_relation_type, rule_version, lot_id,
    ))
    return "lin_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _edge(from_record, to_record, relationship_type, *, basis, confidence,
          reasons, source_ref=None, native_relation_type=None,
          rule_version=LINEAGE_RULE_VERSION):
    from_type = _node_type(from_record)
    to_type = _node_type(to_record)
    if not from_type or not to_type:
        raise ValueError("lineage edges require supported canonical node types")
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError(f"unsupported lineage relationship: {relationship_type}")
    if basis not in BASIS_TYPES or confidence not in CONFIDENCE_TYPES:
        raise ValueError("invalid lineage basis/confidence")

    from_id = _entity_id(from_record)
    to_id = _entity_id(to_record)
    if from_id == to_id:
        raise ValueError("self lineage edge is invalid")

    lot_from = _lot_id(from_record)
    lot_to = _lot_id(to_record)
    if lot_from and lot_to and lot_from != lot_to:
        raise ValueError("cross-lot lineage edge rejected")
    lot_id = lot_from or lot_to

    safe_reasons = tuple(
        _text(reason, limit=_MAX_REASON)
        for reason in reasons
        if _text(reason, limit=_MAX_REASON)
    )
    source_ref = _text(source_ref or "", limit=2000) or None
    native_relation_type = _text(native_relation_type or "", limit=128) or None
    return LineageEdge(
        edge_id=_edge_id(
            from_id, to_id, relationship_type, basis, source_ref,
            native_relation_type, rule_version, lot_id,
        ),
        from_entity_type=from_type,
        from_entity_id=from_id,
        to_entity_type=to_type,
        to_entity_id=to_id,
        relationship_type=relationship_type,
        confidence=confidence,
        basis=basis,
        reasons=safe_reasons,
        source_ref=source_ref,
        native_relation_type=native_relation_type,
        rule_version=rule_version,
        lot_id=lot_id,
    )


def _default_relation(from_type, to_type):
    if from_type == "PROCUREMENT_PLAN" and to_type in {"MARKET_DIALOGUE", "TENDER"}:
        return "PRECEDES"
    if from_type == "MARKET_DIALOGUE" and to_type == "TENDER":
        return "PRECEDES"
    if from_type == "TENDER" and to_type == "AWARD":
        return "RESULTED_IN"
    if from_type == "AWARD" and to_type == "CONTRACT":
        return "CONTRACTED_AS"
    if from_type == "TENDER" and to_type == "CONTRACT":
        return "RELATED_TO"
    if from_type == "AMENDMENT" and to_type == "TENDER":
        return "AMENDS"
    if from_type == "CORRIGENDUM" and to_type in NODE_TYPES:
        return "CORRECTS"
    if _STAGE_ORDER.get(from_type, 100) < _STAGE_ORDER.get(to_type, 100):
        return "PRECEDES"
    return "RELATED_TO"


def _find_record(records_by_id, relation, source):
    target_entity_id = _text(relation.get("target_entity_id") or "")
    if target_entity_id:
        return records_by_id.get(target_entity_id)
    target_source = _text(relation.get("target_source") or source)
    target_external_id = _text(
        relation.get("target_external_id")
        or relation.get("related_notice_id")
        or relation.get("previous_notice_id")
        or ""
    )
    if target_source and target_external_id:
        return records_by_id.get(f"{target_source}:{target_external_id}")
    return None


def _relation_direction(record, target, relationship, relation):
    """Return semantically ordered (from, to) records for an explicit relation.

    `target_is_parent` remains an explicit adapter override. Without that flag,
    action-on-target relations (AMENDS/CORRECTS/SUPERSEDES/DERIVED_FROM) flow
    from the current subject to its target; lifecycle-result relations flow from
    the referenced parent/prior target to the current record.
    """
    if "target_is_parent" in relation:
        target_is_parent = bool(relation.get("target_is_parent"))
    else:
        target_is_parent = relationship not in _SUBJECT_TO_TARGET_RELATIONS
    return (target, record) if target_is_parent else (record, target)


def explicit_relations(records: Sequence[Mapping]):
    records_by_id = {_entity_id(record): record for record in records if _node_type(record)}
    edges = []
    unresolved = []
    for record in records:
        if not _node_type(record):
            continue
        relations = record.get("lineage_relations") or record.get("related_notices") or []
        if not isinstance(relations, list):
            raise ValueError("lineage_relations must be a list")
        for relation in relations:
            if not isinstance(relation, Mapping):
                raise ValueError("lineage relation must be a mapping")
            target = _find_record(records_by_id, relation, _text(record.get("source")))
            if target is None:
                unresolved.append({
                    "from_entity_id": _entity_id(record),
                    "target_source": _text(relation.get("target_source") or record.get("source")),
                    "target_external_id": _text(
                        relation.get("target_external_id")
                        or relation.get("related_notice_id")
                        or relation.get("previous_notice_id")
                        or ""
                    ),
                    "native_relation_type": _text(
                        relation.get("native_relation_type") or relation.get("type") or ""
                    ),
                    "status": "UNRESOLVED",
                    "reason": "explicit target not present in supplied canonical records",
                })
                continue

            relationship = _text(relation.get("relationship_type") or "").upper()
            native_type = _text(
                relation.get("native_relation_type") or relation.get("type") or "",
                limit=128,
            ) or None
            if not relationship:
                relationship = _default_relation(_node_type(target), _node_type(record))
                from_record, to_record = target, record
            else:
                if relationship not in RELATIONSHIP_TYPES:
                    raise ValueError(f"unsupported lineage relationship: {relationship}")
                from_record, to_record = _relation_direction(
                    record, target, relationship, relation
                )
            edges.append(_edge(
                from_record,
                to_record,
                relationship,
                basis="EXPLICIT",
                confidence="HIGH",
                reasons=("source-native relationship",),
                source_ref=(
                    relation.get("source_ref")
                    or record.get("source_reference")
                    or record.get("url")
                ),
                native_relation_type=native_type,
            ))
    return edges, unresolved


def _same_strong_identity(left, right):
    if left["ocid"] and left["ocid"] == right["ocid"]:
        return "same OCDS OCID"
    if (
        left["procurement_reference"]
        and left["procurement_reference"] == right["procurement_reference"]
        and left["jurisdiction"]
        and left["jurisdiction"] == right["jurisdiction"]
    ):
        return "same official procurement reference within jurisdiction"
    return None


def deterministic_relations(records: Sequence[Mapping],
                            existing_edges: Iterable[LineageEdge] = ()):
    canonical = [record for record in records if _node_type(record)]
    snapshots = [_record_snapshot(record) for record in canonical]
    by_id = {snapshot["entity_id"]: record for snapshot, record in zip(snapshots, canonical)}
    existing_pairs = {(edge.from_entity_id, edge.to_entity_id) for edge in existing_edges}

    buckets = {}
    for snapshot in snapshots:
        keys = []
        if snapshot["ocid"]:
            keys.append(("ocid", snapshot["ocid"]))
        if snapshot["procurement_reference"] and snapshot["jurisdiction"]:
            keys.append(("proc", snapshot["jurisdiction"], snapshot["procurement_reference"]))
        for key in keys:
            buckets.setdefault(key, []).append(snapshot)

    output = []
    seen_pairs = set()
    for bucket in buckets.values():
        for index, left in enumerate(bucket):
            for right in bucket[index + 1:]:
                pair_key = tuple(sorted((left["entity_id"], right["entity_id"])))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                if left["entity_type"] == right["entity_type"]:
                    # Same-stage versions belong to Change History unless source-linked.
                    continue
                if left["lot_id"] and right["lot_id"] and left["lot_id"] != right["lot_id"]:
                    continue
                reason = _same_strong_identity(left, right)
                if not reason:
                    continue
                left_order = _STAGE_ORDER[left["entity_type"]]
                right_order = _STAGE_ORDER[right["entity_type"]]
                if left_order == right_order:
                    continue
                parent, child = (
                    (left, right) if left_order < right_order else (right, left)
                )
                if (parent["entity_id"], child["entity_id"]) in existing_pairs:
                    continue
                output.append(_edge(
                    by_id[parent["entity_id"]],
                    by_id[child["entity_id"]],
                    _default_relation(parent["entity_type"], child["entity_type"]),
                    basis="DETERMINISTIC",
                    confidence="HIGH",
                    reasons=(reason,),
                ))
    return output


def candidate_relations(records: Sequence[Mapping],
                        confirmed_edges: Iterable[LineageEdge] = ()):
    canonical = [record for record in records if _node_type(record)]
    snapshots = [_record_snapshot(record) for record in canonical]
    linked = {
        tuple(sorted((edge.from_entity_id, edge.to_entity_id)))
        for edge in confirmed_edges
    }
    buckets = {}
    for snapshot in snapshots:
        key = (snapshot["jurisdiction"], snapshot["buyer_id"] or snapshot["buyer"])
        if all(key):
            buckets.setdefault(key, []).append(snapshot)

    candidates = []
    seen = set()
    for bucket in buckets.values():
        for index, left in enumerate(bucket):
            for right in bucket[index + 1:]:
                pair = tuple(sorted((left["entity_id"], right["entity_id"])))
                if pair in linked or pair in seen:
                    continue
                seen.add(pair)
                if left["lot_id"] and right["lot_id"] and left["lot_id"] != right["lot_id"]:
                    continue
                signals = []
                if left["buyer_id"] and left["buyer_id"] == right["buyer_id"]:
                    signals.append("same buyer identifier")
                elif (
                    left["buyer"] and right["buyer"]
                    and left["buyer"].casefold() == right["buyer"].casefold()
                ):
                    signals.append("same buyer label")
                if (
                    left["title"] and right["title"]
                    and left["title"].casefold() == right["title"].casefold()
                ):
                    signals.append("same normalized title")
                if (
                    left["source_reference"]
                    and left["source_reference"] == right["source_reference"]
                ):
                    signals.append("same source reference")
                if len(signals) >= 2:
                    candidates.append(LineageCandidate(
                        from_entity_id=left["entity_id"],
                        to_entity_id=right["entity_id"],
                        signals=tuple(signals),
                        strength=(
                            "MEDIUM" if "same source reference" in signals else "LOW"
                        ),
                    ))
    candidates.sort(key=lambda candidate: (
        candidate.from_entity_id, candidate.to_entity_id, candidate.signals
    ))
    return candidates


def _has_path(adjacency, start, target):
    stack = [start]
    visited = set()
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adjacency.get(node, ()))
    return False


def reject_cycles(edges: Sequence[LineageEdge]):
    accepted = []
    rejected = []
    adjacency = {}
    for edge in sorted(edges, key=lambda item: (item.basis != "EXPLICIT", item.edge_id)):
        if edge.relationship_type not in DAG_RELATIONSHIP_TYPES:
            accepted.append(edge)
            continue
        if _has_path(adjacency, edge.to_entity_id, edge.from_entity_id):
            rejected.append({
                **edge.as_dict(),
                "status": "REJECTED",
                "reason": "cycle prevented",
            })
            continue
        accepted.append(edge)
        adjacency.setdefault(edge.from_entity_id, set()).add(edge.to_entity_id)
    return accepted, rejected


def detect_lineage_relations(records: Sequence[Mapping], policy: Mapping | None = None):
    """Pure deterministic detector; supplied canonical records are never mutated."""
    del policy  # reserved for a future versioned policy surface
    records = tuple(records or ())
    before = [
        json.dumps(dict(record), sort_keys=True, default=str)
        for record in records
        if isinstance(record, Mapping)
    ]
    explicit, unresolved = explicit_relations(records)
    deterministic = deterministic_relations(records, explicit)
    accepted, rejected = reject_cycles(explicit + deterministic)
    candidates = candidate_relations(records, accepted)
    after = [
        json.dumps(dict(record), sort_keys=True, default=str)
        for record in records
        if isinstance(record, Mapping)
    ]
    if before != after:
        raise RuntimeError("lineage detector mutated source records")
    unique = {edge.edge_id: edge for edge in accepted}
    return {
        "rule_version": LINEAGE_RULE_VERSION,
        "confirmed_relations": [unique[key].as_dict() for key in sorted(unique)],
        "candidates": [candidate.as_dict() for candidate in candidates],
        "unresolved": sorted(
            unresolved, key=lambda item: json.dumps(item, sort_keys=True)
        ),
        "rejected": sorted(rejected, key=lambda item: item["edge_id"]),
    }


def ensure_lineage_tables(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS procurement_lineage_nodes (
        entity_id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        canonical_process_id TEXT,
        jurisdiction TEXT,
        lot_id TEXT,
        event_date TEXT,
        title TEXT,
        source_ref TEXT,
        first_observed TEXT NOT NULL,
        last_observed TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS procurement_lineage_edges (
        edge_id TEXT PRIMARY KEY,
        from_entity_type TEXT NOT NULL,
        from_entity_id TEXT NOT NULL,
        to_entity_type TEXT NOT NULL,
        to_entity_id TEXT NOT NULL,
        relationship_type TEXT NOT NULL,
        confidence TEXT NOT NULL,
        basis TEXT NOT NULL,
        reasons_json TEXT NOT NULL,
        source_ref TEXT,
        native_relation_type TEXT,
        rule_version TEXT NOT NULL,
        lot_id TEXT,
        created_at TEXT NOT NULL
    )''')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lineage_edges_from "
        "ON procurement_lineage_edges(from_entity_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lineage_edges_to "
        "ON procurement_lineage_edges(to_entity_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lineage_nodes_process "
        "ON procurement_lineage_nodes(canonical_process_id, jurisdiction)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lineage_nodes_source "
        "ON procurement_lineage_nodes(source, external_id)"
    )


def _canonical_process_id(snapshot):
    return snapshot["ocid"] or snapshot["procurement_reference"] or None


def persist_lineage_relations(conn, records: Sequence[Mapping],
                              detection: Mapping | None = None, *,
                              observed_at=None, commit=True):
    """Persist additive nodes/confirmed edges idempotently without source mutation."""
    ensure_lineage_tables(conn)
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    canonical_records = [record for record in records if _node_type(record)]
    for record in canonical_records:
        snapshot = _record_snapshot(record)
        conn.execute('''INSERT INTO procurement_lineage_nodes(
            entity_id,entity_type,source,external_id,canonical_process_id,
            jurisdiction,lot_id,event_date,title,source_ref,first_observed,last_observed
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(entity_id) DO UPDATE SET
            entity_type=excluded.entity_type,
            canonical_process_id=COALESCE(
                excluded.canonical_process_id,
                procurement_lineage_nodes.canonical_process_id
            ),
            jurisdiction=excluded.jurisdiction,
            lot_id=excluded.lot_id,
            event_date=excluded.event_date,
            title=excluded.title,
            source_ref=excluded.source_ref,
            last_observed=excluded.last_observed''', (
            snapshot["entity_id"], snapshot["entity_type"], snapshot["source"],
            snapshot["external_id"], _canonical_process_id(snapshot),
            snapshot["jurisdiction"], snapshot["lot_id"], snapshot["event_date"],
            snapshot["title"], snapshot["source_reference"], observed, observed,
        ))

    result = detection or detect_lineage_relations(canonical_records)
    written = 0
    for edge in result.get("confirmed_relations", ()):
        conn.execute('''INSERT OR IGNORE INTO procurement_lineage_edges(
            edge_id,from_entity_type,from_entity_id,to_entity_type,to_entity_id,
            relationship_type,confidence,basis,reasons_json,source_ref,
            native_relation_type,rule_version,lot_id,created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            edge["edge_id"], edge["from_entity_type"], edge["from_entity_id"],
            edge["to_entity_type"], edge["to_entity_id"],
            edge["relationship_type"], edge["confidence"], edge["basis"],
            json.dumps(edge.get("reasons") or [], ensure_ascii=False),
            edge.get("source_ref"), edge.get("native_relation_type"),
            edge.get("rule_version") or LINEAGE_RULE_VERSION,
            edge.get("lot_id"), observed,
        ))
        written += int(conn.execute("SELECT changes()").fetchone()[0])
    if commit:
        conn.commit()
    return {
        "nodes_seen": len(canonical_records),
        "edges_inserted": written,
        "detection": result,
    }


def lineage_view(conn, *, entity_id: str):
    """Build a deterministic connected-family read model around one entity."""
    ensure_lineage_tables(conn)
    entity_id = _text(entity_id)
    seed = conn.execute(
        "SELECT * FROM procurement_lineage_nodes WHERE entity_id=?", (entity_id,)
    ).fetchone()
    if seed is None:
        return None
    seed = dict(seed)

    nodes_by_id = {
        row["entity_id"]: dict(row)
        for row in conn.execute("SELECT * FROM procurement_lineage_nodes").fetchall()
    }
    edge_rows = [
        dict(row)
        for row in conn.execute("SELECT * FROM procurement_lineage_edges").fetchall()
    ]
    adjacency = {}
    for edge in edge_rows:
        adjacency.setdefault(edge["from_entity_id"], set()).add(edge["to_entity_id"])
        adjacency.setdefault(edge["to_entity_id"], set()).add(edge["from_entity_id"])

    family_ids = set()
    stack = [entity_id]
    while stack:
        current = stack.pop()
        if current in family_ids:
            continue
        family_ids.add(current)
        stack.extend(adjacency.get(current, ()))

    family_nodes = [
        nodes_by_id[node_id] for node_id in family_ids if node_id in nodes_by_id
    ]
    family_edges = [
        edge for edge in edge_rows
        if edge["from_entity_id"] in family_ids and edge["to_entity_id"] in family_ids
    ]
    family_nodes.sort(key=lambda node: (
        node.get("event_date") is None,
        node.get("event_date") or "",
        _STAGE_ORDER.get(node.get("entity_type"), 999),
        node["entity_id"],
    ))
    for edge in family_edges:
        edge["reasons"] = json.loads(edge.pop("reasons_json"))
    family_edges.sort(key=lambda edge: edge["edge_id"])

    dated_stages = [
        node["entity_type"] for node in family_nodes if node.get("event_date")
    ]
    return {
        "canonical_process_id": seed.get("canonical_process_id"),
        "jurisdiction": seed.get("jurisdiction"),
        "nodes": family_nodes,
        "relationships": family_edges,
        "timeline": [
            {
                "entity_id": node["entity_id"],
                "entity_type": node["entity_type"],
                "event_date": node.get("event_date"),
                "date_known": bool(node.get("event_date")),
                "title": node.get("title"),
                "lot_id": node.get("lot_id"),
            }
            for node in family_nodes
        ],
        "current_known_stage": dated_stages[-1] if dated_stages else None,
        "coverage_notes": [
            "nodes without a known event date are retained without inventing precise chronology"
        ],
    }
