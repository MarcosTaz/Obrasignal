"""Provenance-first Evidence Graph v1 for ObraSignal.

This module is intentionally an in-process directed acyclic lineage graph. It
adds no graph database and no persistence claim. Consumers can persist exported
snapshots later using existing storage conventions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping

from source_registry import SOURCES

MODEL_VERSION = "evidence-graph-v1"
POLICY_VERSION = "evidence-policy-v1"

MAX_IDENTIFIER_LENGTH = 1024
MAX_LABEL_LENGTH = 2048
MAX_URL_LENGTH = 4096
MAX_SERIALIZED_VALUE_BYTES = 262_144
DEFAULT_MAX_GRAPH_NODES = 10_000
DEFAULT_MAX_GRAPH_EDGES = 50_000


class NodeType(str, Enum):
    EVIDENCE = "EVIDENCE"
    FACT = "FACT"
    ESTIMATE = "ESTIMATE"
    INFERENCE = "INFERENCE"
    ASSUMPTION = "ASSUMPTION"


class EdgeType(str, Enum):
    SUPPORTS = "SUPPORTS"
    DERIVED_FROM = "DERIVED_FROM"
    CONTRADICTS = "CONTRADICTS"
    DEPENDS_ON = "DEPENDS_ON"
    USES_ASSUMPTION = "USES_ASSUMPTION"
    SUPERSEDES = "SUPERSEDES"


class ClaimStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICT = "CONFLICT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    SUPERSEDED = "SUPERSEDED"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


LINEAGE_EDGES = {
    EdgeType.SUPPORTS,
    EdgeType.DERIVED_FROM,
    EdgeType.DEPENDS_ON,
    EdgeType.USES_ASSUMPTION,
}
ACYCLIC_EDGES = LINEAGE_EDGES | {EdgeType.SUPERSEDES}


def _iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _canonical(value: Any) -> Any:
    """Convert nested values to deterministic JSON-compatible structures."""
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [_canonical(v) for v in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    if isinstance(value, datetime):
        return _iso(value)
    return value


def _freeze(value: Any) -> Any:
    """Take an immutable snapshot so node content cannot change retroactively."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(v) for v in value)
    return value


def _view(value: Any) -> Any:
    """Return a detached presentation/export copy of an immutable node value."""
    if isinstance(value, Mapping):
        return {str(k): _view(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_view(v) for v in value]
    if isinstance(value, frozenset):
        return sorted((_view(v) for v in value), key=lambda item: json.dumps(item, sort_keys=True, default=str))
    return value


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    raw = json.dumps(_canonical(payload), ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _bounded_text(name: str, value: Any, *, maximum: int, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    text = str(value).strip()
    if required and not text:
        raise ValueError(f"{name} is required")
    if len(text) > maximum:
        raise ValueError(f"{name} exceeds maximum length")
    if "\x00" in text:
        raise ValueError(f"{name} contains invalid control characters")
    return text


def _assert_serialized_bound(name: str, value: Any) -> None:
    try:
        raw = json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is not serializable") from exc
    if len(raw.encode("utf-8")) > MAX_SERIALIZED_VALUE_BYTES:
        raise ValueError(f"{name} exceeds maximum serialized size")


@dataclass(frozen=True)
class Provenance:
    source: str
    external_id: str
    source_type: str | None = None
    source_url: str | None = None
    publisher: str | None = None
    retrieved_at: str | None = None
    published_at: str | None = None
    effective_at: str | None = None
    raw_identifier: str | None = None
    locator: Mapping[str, Any] = field(default_factory=dict)
    quality: str | None = None
    legal_reuse: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _bounded_text("source", self.source, maximum=MAX_IDENTIFIER_LENGTH, required=True))
        object.__setattr__(self, "external_id", _bounded_text("external_id", self.external_id, maximum=MAX_IDENTIFIER_LENGTH, required=True))
        object.__setattr__(self, "source_type", _bounded_text("source_type", self.source_type, maximum=MAX_IDENTIFIER_LENGTH))
        object.__setattr__(self, "source_url", _bounded_text("source_url", self.source_url, maximum=MAX_URL_LENGTH))
        object.__setattr__(self, "publisher", _bounded_text("publisher", self.publisher, maximum=MAX_LABEL_LENGTH))
        object.__setattr__(self, "raw_identifier", _bounded_text("raw_identifier", self.raw_identifier, maximum=MAX_IDENTIFIER_LENGTH))
        object.__setattr__(self, "quality", _bounded_text("quality", self.quality, maximum=MAX_IDENTIFIER_LENGTH))
        object.__setattr__(self, "legal_reuse", _bounded_text("legal_reuse", self.legal_reuse, maximum=MAX_IDENTIFIER_LENGTH))
        if not isinstance(self.locator, Mapping):
            raise ValueError("locator must be a mapping")
        _assert_serialized_bound("locator", self.locator)
        object.__setattr__(self, "locator", _freeze(dict(self.locator)))
        for field_name in ("retrieved_at", "published_at", "effective_at"):
            raw = getattr(self, field_name)
            if raw in (None, ""):
                object.__setattr__(self, field_name, None)
                continue
            normalized = _iso(raw)
            if normalized is None:
                raise ValueError(f"{field_name} must be ISO-8601")
            object.__setattr__(self, field_name, normalized)

    def identity_key(self) -> tuple:
        return (
            self.source.upper(),
            self.external_id,
            self.raw_identifier or "",
            self.published_at or "",
            self.effective_at or "",
            json.dumps(_canonical(self.locator), sort_keys=True, default=str),
        )


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    tenant_id: str
    provenance: Provenance
    value: Any
    field_name: str | None = None
    unit: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze(self.value))


@dataclass(frozen=True)
class ClaimNode:
    node_id: str
    tenant_id: str
    claim_type: NodeType
    subject: str
    predicate: str
    value: Any = None
    unit: str | None = None
    method: str | None = None
    calculation_version: str | None = None
    valid_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze(self.value))
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata)))


@dataclass(frozen=True)
class Edge:
    source_id: str
    target_id: str
    relation: EdgeType


@dataclass(frozen=True)
class EvidencePolicy:
    version: str = POLICY_VERSION
    default_stale_after_minutes: int = 1440

    def source_quality(self, provenance: Provenance) -> str:
        if provenance.quality:
            return provenance.quality.upper()
        meta = SOURCES.get(provenance.source.upper())
        if not meta:
            return "UNKNOWN"
        if meta.get("official") and meta.get("machine_access") == "VERIFIED" and meta.get("legal_reuse") == "GREEN":
            return "PRIMARY"
        if meta.get("machine_access") == "VERIFIED":
            return "STRUCTURED"
        return "UNKNOWN"

    def stale_after_minutes(self, provenance: Provenance) -> int:
        meta = SOURCES.get(provenance.source.upper())
        if meta and meta.get("stale_after_minutes"):
            value = int(meta["stale_after_minutes"])
            if value <= 0:
                raise ValueError("source stale_after_minutes must be positive")
            return value
        if self.default_stale_after_minutes <= 0:
            raise ValueError("default_stale_after_minutes must be positive")
        return self.default_stale_after_minutes


class EvidenceGraph:
    """Tenant-scoped, deterministic lineage graph with explicit execution bounds."""

    def __init__(
        self,
        tenant_id: str,
        *,
        policy: EvidencePolicy | None = None,
        max_nodes: int = DEFAULT_MAX_GRAPH_NODES,
        max_edges: int = DEFAULT_MAX_GRAPH_EDGES,
    ):
        tenant = _bounded_text("tenant_id", tenant_id, maximum=MAX_IDENTIFIER_LENGTH, required=True)
        if not isinstance(max_nodes, int) or isinstance(max_nodes, bool) or max_nodes <= 0:
            raise ValueError("max_nodes must be a positive integer")
        if not isinstance(max_edges, int) or isinstance(max_edges, bool) or max_edges <= 0:
            raise ValueError("max_edges must be a positive integer")
        self.tenant_id = tenant
        self.policy = policy or EvidencePolicy()
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self.nodes: dict[str, EvidenceNode | ClaimNode] = {}
        self.edges: set[Edge] = set()
        self._evidence_identity: dict[tuple, str] = {}

    def _assert_tenant(self, node: EvidenceNode | ClaimNode) -> None:
        if node.tenant_id != self.tenant_id:
            raise ValueError("cross-tenant evidence graph access denied")

    def _assert_node_capacity(self, node_id: str) -> None:
        if node_id not in self.nodes and len(self.nodes) >= self.max_nodes:
            raise ValueError("evidence graph node limit exceeded")

    def add_evidence(self, provenance: Provenance, value: Any, *, field_name: str | None = None, unit: str | None = None) -> str:
        field_name = _bounded_text("field_name", field_name, maximum=MAX_LABEL_LENGTH)
        unit = _bounded_text("unit", unit, maximum=MAX_IDENTIFIER_LENGTH)
        _assert_serialized_bound("evidence value", value)
        value_snapshot = _freeze(value)
        dedup_key = provenance.identity_key() + (
            field_name or "",
            json.dumps(_canonical(value_snapshot), sort_keys=True, default=str),
        )
        if dedup_key in self._evidence_identity:
            return self._evidence_identity[dedup_key]
        payload = {
            "tenant": self.tenant_id,
            "provenance": provenance.identity_key(),
            "field": field_name,
            "value": _canonical(value_snapshot),
            "unit": unit,
        }
        node_id = _stable_id("ev", payload)
        self._assert_node_capacity(node_id)
        self.nodes[node_id] = EvidenceNode(node_id, self.tenant_id, provenance, value_snapshot, field_name, unit)
        self._evidence_identity[dedup_key] = node_id
        return node_id

    def add_claim(
        self,
        claim_type: NodeType | str,
        subject: str,
        predicate: str,
        value: Any = None,
        *,
        unit: str | None = None,
        method: str | None = None,
        calculation_version: str | None = None,
        valid_at: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        kind = NodeType(claim_type)
        if kind == NodeType.EVIDENCE:
            raise ValueError("use add_evidence for evidence nodes")
        subject = _bounded_text("subject", subject, maximum=MAX_LABEL_LENGTH, required=True)
        predicate = _bounded_text("predicate", predicate, maximum=MAX_LABEL_LENGTH, required=True)
        unit = _bounded_text("unit", unit, maximum=MAX_IDENTIFIER_LENGTH)
        method = _bounded_text("method", method, maximum=MAX_LABEL_LENGTH)
        calculation_version = _bounded_text("calculation_version", calculation_version, maximum=MAX_IDENTIFIER_LENGTH)
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        _assert_serialized_bound("claim value", value)
        _assert_serialized_bound("claim metadata", metadata or {})
        normalized_valid_at = None
        if valid_at not in (None, ""):
            normalized_valid_at = _iso(valid_at)
            if normalized_valid_at is None:
                raise ValueError("valid_at must be ISO-8601")
        value_snapshot = _freeze(value)
        metadata_snapshot = _freeze(dict(metadata or {}))
        payload = {
            "tenant": self.tenant_id,
            "type": kind.value,
            "subject": subject,
            "predicate": predicate,
            "value": _canonical(value_snapshot),
            "unit": unit,
            "method": method,
            "calculation_version": calculation_version,
            "valid_at": normalized_valid_at,
            "metadata": _canonical(metadata_snapshot),
        }
        node_id = _stable_id("cl", payload)
        self._assert_node_capacity(node_id)
        self.nodes.setdefault(
            node_id,
            ClaimNode(
                node_id=node_id,
                tenant_id=self.tenant_id,
                claim_type=kind,
                subject=subject,
                predicate=predicate,
                value=value_snapshot,
                unit=unit,
                method=method,
                calculation_version=calculation_version,
                valid_at=normalized_valid_at,
                metadata=metadata_snapshot,
            ),
        )
        return node_id

    def add_edge(self, source_id: str, target_id: str, relation: EdgeType | str) -> None:
        rel = EdgeType(relation)
        if source_id not in self.nodes or target_id not in self.nodes:
            raise KeyError("edge endpoints must exist")
        self._assert_tenant(self.nodes[source_id])
        self._assert_tenant(self.nodes[target_id])
        candidate = Edge(source_id, target_id, rel)
        if candidate in self.edges:
            return
        if len(self.edges) >= self.max_edges:
            raise ValueError("evidence graph edge limit exceeded")
        if rel in ACYCLIC_EDGES and self._reachable(target_id, source_id, relations=ACYCLIC_EDGES):
            raise ValueError("lineage cycle detected")
        self.edges.add(candidate)

    def _reachable(self, start: str, target: str, *, relations: set[EdgeType]) -> bool:
        stack = [start]
        seen: set[str] = set()
        while stack:
            node_id = stack.pop()
            if node_id == target:
                return True
            if node_id in seen:
                continue
            seen.add(node_id)
            for edge in self.edges:
                if edge.source_id == node_id and edge.relation in relations:
                    stack.append(edge.target_id)
        return False

    def ancestors(self, node_id: str) -> tuple[str, ...]:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        seen: set[str] = set()
        stack = [node_id]
        while stack:
            current = stack.pop()
            for edge in sorted(self.edges, key=lambda e: (e.target_id, e.source_id, e.relation.value)):
                if edge.target_id == current and edge.relation in LINEAGE_EDGES and edge.source_id not in seen:
                    seen.add(edge.source_id)
                    stack.append(edge.source_id)
        return tuple(sorted(seen))

    def _incoming(self, node_id: str, relation: EdgeType | None = None) -> list[Edge]:
        return sorted(
            [e for e in self.edges if e.target_id == node_id and (relation is None or e.relation == relation)],
            key=lambda e: (e.relation.value, e.source_id),
        )

    def _is_stale(self, evidence: EvidenceNode, as_of: datetime) -> bool | None:
        # Observation/retrieval time proves that we saw the record; it does not
        # prove that the publisher's underlying fact is fresh.
        anchor = _dt(evidence.provenance.effective_at) or _dt(evidence.provenance.published_at)
        if not anchor:
            return None
        current = _utc(as_of)
        if anchor > current:
            return None
        age_minutes = (current - anchor).total_seconds() / 60
        return age_minutes > self.policy.stale_after_minutes(evidence.provenance)

    def status(self, claim_id: str, *, as_of: datetime | None = None) -> ClaimStatus:
        node = self.nodes.get(claim_id)
        if not isinstance(node, ClaimNode):
            raise ValueError("status requires a claim node")
        if any(e.relation == EdgeType.SUPERSEDES and e.target_id == claim_id for e in self.edges):
            return ClaimStatus.SUPERSEDED
        if any(e.relation == EdgeType.CONTRADICTS and (e.source_id == claim_id or e.target_id == claim_id) for e in self.edges):
            return ClaimStatus.CONFLICT
        support = self.ancestors(claim_id)
        evidence = [self.nodes[n] for n in support if isinstance(self.nodes[n], EvidenceNode)]
        if node.value is None:
            return ClaimStatus.UNKNOWN
        if node.claim_type == NodeType.FACT and not evidence:
            return ClaimStatus.UNSUPPORTED
        if node.claim_type in {NodeType.ESTIMATE, NodeType.INFERENCE} and not support:
            return ClaimStatus.UNSUPPORTED
        if evidence and as_of is not None and all(self._is_stale(ev, as_of) is True for ev in evidence):
            return ClaimStatus.STALE
        return ClaimStatus.SUPPORTED

    def confidence(self, claim_id: str, *, as_of: datetime | None = None) -> Confidence:
        status = self.status(claim_id, as_of=as_of)
        if status in {ClaimStatus.UNSUPPORTED, ClaimStatus.UNKNOWN}:
            return Confidence.UNKNOWN
        ancestor_ids = self.ancestors(claim_id)
        evidence = [self.nodes[n] for n in ancestor_ids if isinstance(self.nodes[n], EvidenceNode)]
        assumptions = [
            self.nodes[n]
            for n in ancestor_ids
            if isinstance(self.nodes[n], ClaimNode) and self.nodes[n].claim_type == NodeType.ASSUMPTION
        ]
        score = 3
        qualities = {self.policy.source_quality(ev.provenance) for ev in evidence}
        if evidence and qualities <= {"PRIMARY"}:
            score += 1
        elif not evidence:
            score -= 2
        if assumptions:
            score -= min(2, len(assumptions))
        if status == ClaimStatus.CONFLICT:
            score -= 2
        if status == ClaimStatus.STALE:
            score -= 2
        if evidence and as_of is not None and any(self._is_stale(ev, as_of) is None for ev in evidence):
            score -= 1
        if self._max_depth(claim_id) >= 4:
            score -= 1
        return Confidence.HIGH if score >= 4 else Confidence.MEDIUM if score >= 2 else Confidence.LOW

    def _max_depth(self, node_id: str) -> int:
        max_depth = 0
        stack: list[tuple[str, int]] = [(node_id, 0)]
        deepest_seen: dict[str, int] = {}
        while stack:
            current, depth = stack.pop()
            if depth <= deepest_seen.get(current, -1):
                continue
            deepest_seen[current] = depth
            max_depth = max(max_depth, depth)
            for edge in self._incoming(current):
                if edge.relation in LINEAGE_EDGES:
                    stack.append((edge.source_id, depth + 1))
        return max_depth

    def explain(self, claim_id: str, *, as_of: datetime | None = None) -> dict[str, Any]:
        node = self.nodes.get(claim_id)
        if not isinstance(node, ClaimNode):
            raise ValueError("explain requires a claim node")
        ancestor_ids = self.ancestors(claim_id)
        ancestors = [self.nodes[n] for n in ancestor_ids]
        claims = [n for n in ancestors if isinstance(n, ClaimNode)]
        evidence = [n for n in ancestors if isinstance(n, EvidenceNode)]
        lineage_scope = set(ancestor_ids) | {claim_id}
        conflicts = [
            {"left": edge.source_id, "right": edge.target_id}
            for edge in sorted(self.edges, key=lambda e: (e.relation.value, e.source_id, e.target_id))
            if edge.relation == EdgeType.CONTRADICTS
            and (edge.source_id in lineage_scope or edge.target_id in lineage_scope)
        ]
        st = self.status(claim_id, as_of=as_of)
        missing: list[str] = []
        if st == ClaimStatus.UNSUPPORTED:
            missing.append("material_support")
        if st == ClaimStatus.UNKNOWN:
            missing.append("claim_value")
        if evidence and as_of is not None and any(self._is_stale(ev, as_of) is None for ev in evidence):
            missing.append("source_freshness")
        return {
            "claim": self._claim_view(node),
            "status": st.value,
            "confidence": self.confidence(claim_id, as_of=as_of).value,
            "facts": [self._claim_view(n) for n in claims if n.claim_type == NodeType.FACT],
            "estimates": [self._claim_view(n) for n in claims if n.claim_type == NodeType.ESTIMATE],
            "inferences": [self._claim_view(n) for n in claims if n.claim_type == NodeType.INFERENCE],
            "assumptions": [self._claim_view(n) for n in claims if n.claim_type == NodeType.ASSUMPTION],
            "evidence": [self._evidence_view(n, as_of=as_of) for n in evidence],
            "conflicts": conflicts,
            "missing": missing,
            "dependencies": list(ancestor_ids),
            "model_version": MODEL_VERSION,
            "policy_version": self.policy.version,
        }

    def _claim_view(self, node: ClaimNode) -> dict[str, Any]:
        return {
            "claim_id": node.node_id,
            "type": node.claim_type.value,
            "subject": node.subject,
            "predicate": node.predicate,
            "value": _view(node.value),
            "unit": node.unit,
            "method": node.method,
            "calculation_version": node.calculation_version,
            "valid_at": node.valid_at,
            "metadata": _view(node.metadata),
        }

    def _evidence_view(self, node: EvidenceNode, *, as_of: datetime | None) -> dict[str, Any]:
        p = node.provenance
        return {
            "evidence_id": node.node_id,
            "source": p.source,
            "external_id": p.external_id,
            "source_type": p.source_type,
            "source_url": p.source_url,
            "publisher": p.publisher,
            "retrieved_at": p.retrieved_at,
            "published_at": p.published_at,
            "effective_at": p.effective_at,
            "raw_identifier": p.raw_identifier,
            "locator": _view(p.locator),
            "field_name": node.field_name,
            "value": _view(node.value),
            "unit": node.unit,
            "quality": self.policy.source_quality(p),
            "legal_reuse": p.legal_reuse,
            "stale": self._is_stale(node, as_of) if as_of is not None else None,
        }

    def export(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "model_version": MODEL_VERSION,
            "policy_version": self.policy.version,
            "nodes": [self._serialize_node(self.nodes[key]) for key in sorted(self.nodes)],
            "edges": [
                {"source_id": e.source_id, "target_id": e.target_id, "relation": e.relation.value}
                for e in sorted(self.edges, key=lambda e: (e.source_id, e.target_id, e.relation.value))
            ],
        }

    def _serialize_node(self, node: EvidenceNode | ClaimNode) -> dict[str, Any]:
        if isinstance(node, EvidenceNode):
            return {"node_type": NodeType.EVIDENCE.value, **self._evidence_view(node, as_of=None)}
        return {"node_type": node.claim_type.value, **self._claim_view(node)}


def signal_to_fact(
    graph: EvidenceGraph,
    signal: Mapping[str, Any],
    field_name: str,
    *,
    subject: str | None = None,
    publisher: str | None = None,
    retrieved_at: Any = None,
) -> str:
    """Generic Signal -> Evidence -> FACT adapter; connectors need no graph knowledge."""
    source = str(signal.get("source") or "").strip()
    external_id = str(signal.get("external_id") or "").strip()
    if not source or not external_id:
        raise ValueError("signal source/external_id are required")
    value = signal.get(field_name)
    provenance = Provenance(
        source=source,
        external_id=external_id,
        source_type=str(signal.get("signal_type") or "TENDER"),
        source_url=signal.get("url"),
        publisher=publisher,
        retrieved_at=retrieved_at or signal.get("last_observed"),
        published_at=signal.get("published_at") or signal.get("publication_date"),
        effective_at=signal.get("source_updated_at"),
        raw_identifier=str(signal.get("source_reference") or external_id),
        locator={"field": field_name},
        legal_reuse=(SOURCES.get(source.upper()) or {}).get("legal_reuse"),
    )
    evidence_id = graph.add_evidence(provenance, value, field_name=field_name)
    claim_id = graph.add_claim(
        NodeType.FACT,
        subject or external_id,
        field_name,
        value,
        valid_at=provenance.effective_at or provenance.published_at,
    )
    graph.add_edge(evidence_id, claim_id, EdgeType.SUPPORTS)
    return claim_id


def _signal_dependency(graph: EvidenceGraph, signal: Mapping[str, Any], field_name: str, subject: str) -> str:
    """Represent a calculation input even when the normalized Signal lacks it."""
    if field_name in signal and signal.get(field_name) is not None:
        return signal_to_fact(graph, signal, field_name, subject=subject)
    return graph.add_claim(NodeType.FACT, subject, field_name, None, metadata={"missing": True})


def economic_fit_lineage(
    graph: EvidenceGraph,
    signal: Mapping[str, Any],
    profile: Mapping[str, Any],
    economic_result: Mapping[str, Any],
) -> str:
    """Minimal demonstration adapter for ``economic_fit.evaluate_economic_fit`` output.

    It records every material Signal/profile dependency used by the current
    economic-fit rule family, while leaving the existing economic engine intact.
    """
    opportunity_id = str(signal.get("external_id") or "opportunity")
    dependencies = [_signal_dependency(graph, signal, "value", opportunity_id)]

    deadline_rules = any(profile.get(key) is not None for key in ("min_deadline_days", "max_deadline_days"))
    procedure_rules = bool(profile.get("preferred_procedure_types") or profile.get("excluded_procedure_types"))
    if deadline_rules:
        dependencies.append(_signal_dependency(graph, signal, "deadline", opportunity_id))
    if procedure_rules:
        dependencies.append(_signal_dependency(graph, signal, "procedure_type", opportunity_id))

    profile_keys = (
        "min_value",
        "max_value",
        "min_deadline_days",
        "max_deadline_days",
        "economic_min_score",
        "preferred_procedure_types",
        "excluded_procedure_types",
    )
    for key in profile_keys:
        value = profile.get(key)
        if value is not None and value != [] and value != () and value != set():
            dependencies.append(
                graph.add_claim(
                    NodeType.ASSUMPTION,
                    opportunity_id,
                    f"company_rule.{key}",
                    value,
                    method="company_profile",
                )
            )

    estimate_id = graph.add_claim(
        NodeType.ESTIMATE,
        opportunity_id,
        "economic_fit.score",
        economic_result.get("score"),
        unit="/100",
        method="evaluate_economic_fit",
        calculation_version=economic_result.get("rule_version"),
        metadata={
            "status": economic_result.get("status"),
            "reason": economic_result.get("reason"),
            "rules": economic_result.get("rules") or [],
        },
    )
    for dependency in dependencies:
        dependency_node = graph.nodes[dependency]
        relation = (
            EdgeType.USES_ASSUMPTION
            if isinstance(dependency_node, ClaimNode) and dependency_node.claim_type == NodeType.ASSUMPTION
            else EdgeType.DERIVED_FROM
        )
        graph.add_edge(dependency, estimate_id, relation)

    inference_id = graph.add_claim(
        NodeType.INFERENCE,
        opportunity_id,
        "economic_fit.assessment",
        economic_result.get("status"),
        method="economic_fit_policy",
        calculation_version=economic_result.get("rule_version"),
        metadata={"reason": economic_result.get("reason")},
    )
    graph.add_edge(estimate_id, inference_id, EdgeType.DERIVED_FROM)
    return inference_id
