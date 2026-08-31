from __future__ import annotations

import difflib
import hashlib
import platform
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from vertical_apps.industrial_claims.proof import sha256_hex, sha512_hex


@dataclass(frozen=True)
class CausalEdge:
    edge_type: str
    from_ref: str
    to_ref: str
    evidence_ids: tuple[str, ...]
    state: str = "SUPPORTED"

    def as_dict(self) -> dict[str, Any]:
        if not self.edge_type or not self.from_ref or not self.to_ref or not self.evidence_ids:
            raise ValueError("causal edges require type, endpoints and supporting evidence")
        if self.state not in {"SUPPORTED", "WEAK", "CONTRADICTED", "UNRESOLVED"}:
            raise ValueError("invalid causal edge state")
        return {
            "edge_type": self.edge_type,
            "from_ref": self.from_ref,
            "to_ref": self.to_ref,
            "evidence_ids": list(self.evidence_ids),
            "state": self.state,
        }


def dual_digest(content: bytes | bytearray | memoryview | str) -> dict[str, Any]:
    payload = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "sha512": hashlib.sha512(payload).hexdigest(),
        "byte_length": len(payload),
    }


def signed_semantic_diff_payload(*, before_ref: str, after_ref: str, before_text: str, after_text: str) -> dict[str, Any]:
    """Create a deterministic diff payload that can later be externally signed/sealed."""
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    unified = list(difflib.unified_diff(before_lines, after_lines, fromfile=before_ref, tofile=after_ref, lineterm=""))
    body = {
        "before_ref": before_ref,
        "after_ref": after_ref,
        "before_hashes": dual_digest(before_text),
        "after_hashes": dual_digest(after_text),
        "unified_diff": unified,
        "interpretation": "TEXTUAL_DIFF_ONLY_REQUIRES_HUMAN_OR_DOMAIN_REVIEW_FOR_COMMERCIAL_MEANING",
    }
    return {**body, "diff_sha256": sha256_hex(body), "diff_sha512": sha512_hex(body)}


def build_causal_graph(edges: Iterable[CausalEdge]) -> dict[str, Any]:
    items = [edge.as_dict() for edge in edges]
    body = {
        "model": "REQUEST->CHANGE->WORK->RESOURCE->COST->CONTRACT_BASIS->NOTICE->RECOVERY",
        "edges": items,
        "all_edges_require_evidence": True,
    }
    return {**body, "graph_sha256": sha256_hex(body)}


def adverse_evidence_register(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = []
    for item in items:
        evidence_id = str(item.get("evidence_id") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not evidence_id or not reason:
            raise ValueError("adverse evidence requires evidence_id and reason")
        normalized.append({
            "evidence_id": evidence_id,
            "reason": reason,
            "impact": str(item.get("impact") or "REQUIRES_REVIEW"),
        })
    body = {
        "items": normalized,
        "absence_of_items_does_not_prove_no_adverse_evidence_exists": True,
        "must_not_be_silently_removed": True,
    }
    return {**body, "register_sha256": sha256_hex(body)}


def calculation_provenance(*, calculation: Mapping[str, Any], engine_version: str, ruleset_hash: str | None = None) -> dict[str, Any]:
    body = {
        "calculation": dict(calculation),
        "engine_version": engine_version,
        "ruleset_hash": ruleset_hash,
        "reproducible_without_causledger": True,
    }
    return {**body, "provenance_sha256": sha256_hex(body)}


def software_provenance(*, source_revision: str, build_hash: str, ruleset_hash: str | None = None, runtime: str | None = None) -> dict[str, Any]:
    body = {
        "source_revision": source_revision,
        "build_hash": build_hash,
        "ruleset_hash": ruleset_hash,
        "runtime": runtime or f"Python {platform.python_version()}",
        "software_provenance_establishes_correct_execution": False,
    }
    return {**body, "software_provenance_sha256": sha256_hex(body)}


def build_evidence_certificate(*, manifest: Mapping[str, Any], evidence_id: str, certificate_id: str) -> dict[str, Any]:
    evidence = [item for item in manifest.get("evidence", []) if item.get("evidence_id") == evidence_id]
    if len(evidence) != 1:
        raise ValueError("evidence certificate requires exactly one manifest evidence item")
    item = evidence[0]
    body = {
        "certificate_id": certificate_id,
        "proof_system": "CausLedger Evidence Certificate",
        "evidence_id": evidence_id,
        "tenant_id": manifest.get("tenant_id"),
        "finding_id": manifest.get("finding_id"),
        "received_at": item.get("received_at"),
        "source_type": item.get("source_type"),
        "source_ref": item.get("source_ref"),
        "hashes": item.get("hashes"),
        "assurance_state": item.get("assurance_state"),
        "assurance_dimensions": item.get("assurance_dimensions"),
        "integrity_truth_boundary": {
            "integrity_may_be_proven": True,
            "factual_truth_not_created_by_hashing": True,
            "commercial_responsibility_not_determined_by_certificate": True,
        },
    }
    return {**body, "certificate_sha256": sha256_hex(body), "certificate_sha512": sha512_hex(body)}
