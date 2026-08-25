"""Decision-lineage adapter between commercial evaluation and Evidence Graph v1.

The graph remains a reusable domain model.  This module owns the product
boundary: construct one bounded account-scoped lineage snapshot for a persisted
commercial decision and derive a compact customer-safe view from it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from evidence_graph import EdgeType, EvidenceGraph, NodeType, signal_to_fact

EVIDENCE_CONTRACT_VERSION = "evidence.v1"
DECISION_GRAPH_MAX_NODES = 128
DECISION_GRAPH_MAX_EDGES = 512

_SIGNAL_FIELDS = (
    "title",
    "description",
    "buyer",
    "country",
    "cpv",
    "value",
    "deadline",
    "procedure_type",
)
_PROFILE_FIELDS = (
    "activity",
    "contract_interests",
    "keywords",
    "countries",
    "cpv_prefixes",
    "min_value",
    "max_value",
    "economic_min_score",
    "min_deadline_days",
    "max_deadline_days",
    "preferred_procedure_types",
    "excluded_procedure_types",
    "exclude_keywords",
    "regions",
    "geographic_radius_km",
    "services",
    "capability_tags",
    "project_scales",
    "certifications",
    "hard_exclusions",
)


def _as_of(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif value:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("decided_at must be ISO-8601") from exc
    else:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _signal_view(row: Mapping[str, Any]) -> dict[str, Any]:
    source = str(row.get("source") or "").strip()
    external_id = str(row.get("external_id") or row.get("id") or "").strip()
    if not source or not external_id:
        raise ValueError("decision evidence requires source and external_id")
    return {
        "source": source,
        "signal_type": str(row.get("signal_type") or "TENDER").strip().upper(),
        "external_id": external_id,
        "title": row.get("title"),
        "description": row.get("description"),
        "buyer": row.get("buyer"),
        "country": row.get("country"),
        "cpv": row.get("cpv"),
        "value": row.get("value_numeric") if row.get("value_numeric") is not None else row.get("value"),
        "deadline": row.get("deadline"),
        "procedure_type": row.get("procedure_type") or row.get("notice_type"),
        "url": row.get("url"),
        "source_reference": row.get("source_reference") or external_id,
        "published_at": row.get("published_at") or row.get("publication_date"),
        "source_updated_at": row.get("source_updated_at") or row.get("lifecycle_source_updated_at"),
        "last_observed": row.get("last_observed") or row.get("lifecycle_last_observed") or row.get("last_seen"),
    }


def _profile_snapshot(profile: Mapping[str, Any], evaluation: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = {key: profile.get(key) for key in _PROFILE_FIELDS if profile.get(key) not in (None, "", [], (), {})}
    # Capability profile is normalized and therefore often more useful for
    # replay than legacy aliases in the raw company profile.
    capability = evaluation.get("capability")
    if isinstance(capability, Mapping):
        snapshot["normalized_capability"] = dict(capability)
    return snapshot


def _input_fact(graph: EvidenceGraph, signal: Mapping[str, Any], field_name: str) -> tuple[str, bool]:
    value = signal.get(field_name)
    subject = str(signal["external_id"])
    if value is None or value == "":
        return (
            graph.add_claim(
                NodeType.FACT,
                subject,
                field_name,
                None,
                metadata={"missing": True, "source": signal["source"]},
            ),
            True,
        )
    return signal_to_fact(graph, signal, field_name, subject=subject), False


def _derived_claim(
    graph: EvidenceGraph,
    *,
    subject: str,
    predicate: str,
    value: Any,
    method: str,
    rule_version: str,
    dependencies: list[str],
    metadata: Mapping[str, Any] | None = None,
    inference: bool = False,
) -> str:
    claim_id = graph.add_claim(
        NodeType.INFERENCE if inference else NodeType.ESTIMATE,
        subject,
        predicate,
        value,
        method=method,
        calculation_version=rule_version,
        metadata=metadata or {},
    )
    for dependency in dependencies:
        graph.add_edge(dependency, claim_id, EdgeType.DERIVED_FROM)
    return claim_id


def build_decision_evidence(
    account_id: str,
    row: Mapping[str, Any],
    profile: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    *,
    rule_version: str,
    decided_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Build one bounded immutable decision snapshot suitable for persistence."""
    signal = _signal_view(row)
    graph = EvidenceGraph(
        account_id,
        max_nodes=DECISION_GRAPH_MAX_NODES,
        max_edges=DECISION_GRAPH_MAX_EDGES,
    )
    subject = signal["external_id"]
    input_claims: dict[str, str] = {}
    missing_inputs: list[str] = []
    for field_name in _SIGNAL_FIELDS:
        claim_id, missing = _input_fact(graph, signal, field_name)
        input_claims[field_name] = claim_id
        if missing:
            missing_inputs.append(field_name)

    profile_claim = graph.add_claim(
        NodeType.ASSUMPTION,
        subject,
        "company_profile.snapshot",
        _profile_snapshot(profile, evaluation),
        method="company_profile",
        calculation_version="company-profile-current",
        metadata={"scope": "account_private"},
    )

    profile_score = _derived_claim(
        graph,
        subject=subject,
        predicate="commercial.profile_score",
        value=evaluation.get("profile_score"),
        method="personalized_score",
        rule_version=rule_version,
        dependencies=[input_claims["title"], input_claims["description"], input_claims["buyer"], input_claims["country"], input_claims["cpv"], input_claims["value"], profile_claim],
    )
    lot_score = _derived_claim(
        graph,
        subject=subject,
        predicate="commercial.lot_score",
        value=evaluation.get("lot_score"),
        method="match_lot",
        rule_version=rule_version,
        dependencies=list(input_claims.values()) + [profile_claim],
    )
    geography = evaluation.get("geography") or {}
    geography_claim = _derived_claim(
        graph,
        subject=subject,
        predicate="commercial.geography",
        value=geography.get("reason"),
        method="match_lot.geography",
        rule_version=rule_version,
        dependencies=[input_claims["country"], profile_claim],
        metadata={"score": geography.get("score")},
        inference=True,
    )
    capability_evidence = evaluation.get("capability_evidence") or {}
    capability_claim = _derived_claim(
        graph,
        subject=subject,
        predicate="commercial.capability",
        value=capability_evidence.get("status") or ("MATCH" if capability_evidence.get("matched") else "UNKNOWN"),
        method="capability_matches_text",
        rule_version=rule_version,
        dependencies=[input_claims["title"], input_claims["description"], profile_claim],
        metadata={
            "reason": capability_evidence.get("reason"),
            "matched_services": capability_evidence.get("matched_services") or [],
            "evidence_count": capability_evidence.get("evidence_count"),
        },
        inference=True,
    )
    cpv_evidence = evaluation.get("cpv_evidence") or {}
    cpv_claim = _derived_claim(
        graph,
        subject=subject,
        predicate="commercial.cpv",
        value=cpv_evidence.get("status") or "UNKNOWN",
        method="cpv_evidence",
        rule_version=rule_version,
        dependencies=[input_claims["cpv"], profile_claim],
        metadata={
            "reason": cpv_evidence.get("reason"),
            "strength": cpv_evidence.get("strength"),
            "matched_prefixes": cpv_evidence.get("matched_prefixes") or [],
        },
        inference=True,
    )
    economics = evaluation.get("economic_fit") or {}
    economic_claim = _derived_claim(
        graph,
        subject=subject,
        predicate="economic_fit.assessment",
        value=economics.get("status") or "UNKNOWN",
        method="evaluate_economic_fit",
        rule_version=str(economics.get("rule_version") or rule_version),
        dependencies=[input_claims["value"], input_claims["deadline"], input_claims["procedure_type"], profile_claim],
        metadata={
            "score": economics.get("score"),
            "reason": economics.get("reason"),
            "rules": economics.get("rules") or [],
        },
        inference=True,
    )
    blockers = list(evaluation.get("hard_capability_blockers") or [])
    blocker_claim = _derived_claim(
        graph,
        subject=subject,
        predicate="commercial.hard_blockers",
        value=blockers,
        method="hard_capability_checks",
        rule_version=rule_version,
        dependencies=[lot_score, geography_claim, capability_claim, cpv_claim, economic_claim],
        metadata={"count": len(blockers)},
        inference=True,
    )
    decision_claim = _derived_claim(
        graph,
        subject=subject,
        predicate="commercial.decision",
        value=evaluation.get("decision"),
        method="evaluate_row",
        rule_version=rule_version,
        dependencies=[profile_score, lot_score, geography_claim, capability_claim, cpv_claim, economic_claim, blocker_claim],
        metadata={
            "reason": evaluation.get("reason"),
            "profile_score": evaluation.get("profile_score"),
            "lot_score": evaluation.get("lot_score"),
            "blockers": blockers,
        },
        inference=True,
    )

    as_of = _as_of(decided_at)
    return {
        "contract_version": EVIDENCE_CONTRACT_VERSION,
        "state": "READY",
        "decision_claim_id": decision_claim,
        "missing_inputs": sorted(missing_inputs),
        "explanation": graph.explain(decision_claim, as_of=as_of),
        "graph": graph.export(),
    }


def unavailable_decision_evidence(reason: str = "evidence_contract_rejected") -> dict[str, Any]:
    return {
        "contract_version": EVIDENCE_CONTRACT_VERSION,
        "state": "UNAVAILABLE",
        "reason": str(reason),
    }


def customer_evidence_view(snapshot: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return the compact authenticated product view; never expose raw profile snapshots."""
    if not isinstance(snapshot, Mapping):
        return None
    state = str(snapshot.get("state") or "UNAVAILABLE")
    if state != "READY":
        return {
            "contract_version": snapshot.get("contract_version") or EVIDENCE_CONTRACT_VERSION,
            "state": "UNAVAILABLE",
            "reason": snapshot.get("reason") or "evidence_unavailable",
        }

    explanation = snapshot.get("explanation")
    if not isinstance(explanation, Mapping):
        return unavailable_decision_evidence("evidence_snapshot_invalid")

    seen: set[tuple[str, str, str | None]] = set()
    sources: list[dict[str, Any]] = []
    for item in explanation.get("evidence") or []:
        if not isinstance(item, Mapping):
            continue
        key = (str(item.get("source") or ""), str(item.get("external_id") or ""), item.get("field_name"))
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "source": item.get("source"),
            "external_id": item.get("external_id"),
            "publisher": item.get("publisher"),
            "field_name": item.get("field_name"),
            "published_at": item.get("published_at"),
            "effective_at": item.get("effective_at"),
            "retrieved_at": item.get("retrieved_at"),
            "source_url": item.get("source_url"),
            "quality": item.get("quality"),
            "stale": item.get("stale"),
        })
        if len(sources) >= 12:
            break

    missing = sorted({str(value) for value in (snapshot.get("missing_inputs") or []) + (explanation.get("missing") or []) if value})
    return {
        "contract_version": snapshot.get("contract_version") or EVIDENCE_CONTRACT_VERSION,
        "state": "READY",
        "status": explanation.get("status"),
        "confidence": explanation.get("confidence"),
        "sources": sources,
        "missing": missing,
        "conflict_count": len(explanation.get("conflicts") or []),
        "model_version": explanation.get("model_version"),
        "policy_version": explanation.get("policy_version"),
        "decision_claim_id": snapshot.get("decision_claim_id"),
    }
