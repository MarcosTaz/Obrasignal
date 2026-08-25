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
from typing import Any, Mapping

from source_registry import SOURCES

MODEL_VERSION = "evidence-graph-v1"
POLICY_VERSION = "evidence-policy-v1"


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
            return str(value)
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


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


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

    def identity_key(self) -> tuple:
        return (
            self.source.strip().upper(),
            self.external_id.strip(),
            self.raw_identifier or "",
            json.dumps(dict(self.locator), sort_keys=True, default=str),
        )


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    tenant_id: str
    provenance: Provenance
    value: Any
    field_name: str | None = None
    unit: str | None = None


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
            return int(meta["stale_after_minutes"])
        return self.default_stale_after_minutes


class EvidenceGraph:
    """Tenant-scoped, deterministic lineage graph.

    IDs are content-derived. Freshness is deterministic for the same explicit
    ``as_of`` value and policy version.
    """

    def __init__(self, tenant_id: str, *, policy: EvidencePolicy | None = None):
        self.tenant_id = str(tenant_id or "default")
        self.policy = policy or EvidencePolicy()
        self.nodes: dict[str, EvidenceNode | ClaimNode] = {}
        self.edges: set[Edge] = set()
        self._evidence_identity: dict[tuple, str] = {}

    def _assert_tenant(self, node: EvidenceNode | ClaimNode) -> None:
        if node.tenant_id != self.tenant_id:
            raise ValueError("cross-tenant evidence graph access denied")

    def add_evidence(self, provenance: Provenance, value: Any, *, field_name: str | None = None, unit: str | None = None) -> str:
        if not provenance.source.strip() or not provenance.external_id.strip():
            raise ValueError("evidence source and external_id are required")
        dedup_key = provenance.identity_key() + (field_name or "", json.dumps(value, sort_keys=True, default=str))
        if dedup_key in self._evidence_identity:
            return self._evidence_identity[dedup_key]
        payload = {
            "tenant": self.tenant_id,
            "provenance": provenance.identity_key(),
            "field": field_name,
            "value": value,
            "unit": unit,
        }
        node_id = _stable_id("ev", payload)
        node = EvidenceNode(node_id, self.tenant_id, provenance, value, field_name, unit)
        self.nodes[node_id] = node
        self._evidence_identity[dedup_key] = node_id
        return node_id

    def add_claim(self, claim_type: NodeType | str, subject: str, predicate: str, value: Any = None, *, unit: str | None = None, method: str | None = None, calculation_version: str | None = None, valid_at: Any = None, metadata: Mapping[str, Any] | None = None) -> str:
        kind = NodeType(claim_type)
        if kind == NodeType.EVIDENCE:
            raise ValueError("use add_evidence for evidence nodes")
        payload = {
            "tenant": self.tenant_id,
            "type": kind.value,
            "subject": subject,
            "predicate": predicate,
            "value": value,
            "unit": unit,
            "method": method,
            "calculation_version": calculation_version,
            "valid_at": _iso(valid_at),
            "metadata": dict(metadata or {}),
        }
        node_id = _stable_id("cl", payload)
        self.nodes.setdefault(
            node_id,
            ClaimNode(
                node_id=node_id,
                tenant_id=self.tenant_id,
                claim_type=kind,
                subject=str(subject),
                predicate=str(predicate),
                value=value,
                unit=unit,
                method=method,
                calculation_version=calculation_version,
                valid_at=_iso(valid_at),
                metadata=dict(metadata or {}),
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

    def _is_stale(self, evidence: EvidenceNode, as_of: datetime) -> bool:
        # Reading old material now must not make it current: prefer source time;
        # retrieved_at is only a fallback when source time is unavailable.
        anchor = _dt(evidence.provenance.effective_at) or _dt(evidence.provenance.published_at) or _dt(evidence.provenance.retrieved_at)
        if not anchor:
            return False
        age_minutes = (_utc(as_of) - anchor).total_seconds() / 60
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
        if evidence and as_of is not None and all(self._is_stale(ev, as_of) for ev in evidence):
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
        depth = self._max_depth(claim_id)
        if depth >= 4:
            score -= 1
        return Confidence.HIGH if score >= 4 else Confidence.MEDIUM if score >= 2 else Confidence.LOW

    def _max_depth(self, node_id: str) -> int:
        memo: dict[str, int] = {}

        def walk(n: str) -> int:
            if n in memo:
                return memo[n]
            incoming = [e.source_id for e in self._incoming(n) if e.relation in LINEAGE_EDGES]
            memo[n] = 0 if not incoming else 1 + max(walk(parent) for parent in incoming)
            return memo[n]

        return walk(node_id)

    def explain(self, claim_id: str, *, as_of: datetime | None = None) -> dict[str, Any]:
        node = self.nodes.get(claim_id)
        if not isinstance(node, ClaimNode):
            raise ValueError("explain requires a claim node")
        ancestor_ids = self.ancestors(claim_id)
        ancestors = [self.nodes[n] for n in ancestor_ids]
        claims = [n for n in ancestors if isinstance(n, ClaimNode)]
        evidence = [n for n in ancestors if isinstance(n, EvidenceNode)]
        conflicts = []
        lineage_scope = set(ancestor_ids) | {claim_id}
        for edge in sorted(self.edges, key=lambda e: (e.relation.value, e.source_id, e.target_id)):
            if edge.relation == EdgeType.CONTRADICTS and (edge.source_id in lineage_scope or edge.target_id in lineage_scope):
                conflicts.append({"left": edge.source_id, "right": edge.target_id})
        missing = []
        st = self.status(claim_id, as_of=as_of)
        if st == ClaimStatus.UNSUPPORTED:
            missing.append("material_support")
        if st == ClaimStatus.UNKNOWN:
            missing.append("claim_value")
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
            "value": node.value,
            "unit": node.unit,
            "method": node.method,
            "calculation_version": node.calculation_version,
            "valid_at": node.valid_at,
            "metadata": dict(node.metadata),
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
            "locator": dict(p.locator),
            "field_name": node.field_name,
            "value": node.value,
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


def signal_to_fact(graph: EvidenceGraph, signal: Mapping[str, Any], field_name: str, *, subject: str | None = None, publisher: str | None = None, retrieved_at: Any = None) -> str:
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
        retrieved_at=_iso(retrieved_at or signal.get("last_observed")),
        published_at=_iso(signal.get("published_at") or signal.get("publication_date")),
        effective_at=_iso(signal.get("source_updated_at")),
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


def economic_fit_lineage(graph: EvidenceGraph, signal: Mapping[str, Any], profile: Mapping[str, Any], economic_result: Mapping[str, Any]) -> str:
    """Minimal demonstration adapter for ``economic_fit.evaluate_economic_fit`` output."""
    opportunity_id = str(signal.get("external_id") or "opportunity")
    value_fact = signal_to_fact(graph, signal, "value", subject=opportunity_id)
    dependencies = [value_fact]
    for key in ("min_value", "max_value", "min_deadline_days", "max_deadline_days", "economic_min_score"):
        if profile.get(key) is not None:
            assumption_id = graph.add_claim(
                NodeType.ASSUMPTION,
                opportunity_id,
                f"company_rule.{key}",
                profile[key],
                method="company_profile",
            )
            dependencies.append(assumption_id)
    estimate_id = graph.add_claim(
        NodeType.ESTIMATE,
        opportunity_id,
        "economic_fit.score",
        economic_result.get("score"),
        unit="/100",
        method="evaluate_economic_fit",
        calculation_version=economic_result.get("rule_version"),
        metadata={"status": economic_result.get("status"), "reason": economic_result.get("reason")},
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
