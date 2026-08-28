from __future__ import annotations

import hashlib
import json
from typing import Any

from engine import analyze_case


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _identity_hash(payload: dict[str, Any]) -> str:
    return _canonical_hash(payload)


def recovery_identity(case: dict[str, Any]) -> dict[str, str]:
    record = {
        "tenant_id": case.get("tenant_id"),
        "change_id": case.get("change_id"),
    }
    technical_delta = {
        "tenant_id": case.get("tenant_id"),
        "customer": case.get("customer"),
        "program": case.get("program"),
        "part": case.get("part"),
        "revision_from": case.get("revision_from"),
        "revision_to": case.get("revision_to"),
    }
    return {
        "change_record_key": _identity_hash(record),
        "technical_delta_key": _identity_hash(technical_delta),
    }


def build_commercial_package(case: dict[str, Any], analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis = analysis or analyze_case(case)
    entitlement = case.get("entitlement") or {}
    evidence = case.get("evidence") or []
    costs = case.get("costs") or []

    cost_impact = []
    for cost in costs:
        cost_impact.append({
            "id": cost.get("id"),
            "class": cost.get("class"),
            "amount": cost.get("amount"),
            "currency": cost.get("currency") or analysis.get("currency"),
            "causal_state": cost.get("causal_state") or "UNKNOWN",
            "attribution_pct": cost.get("attribution_pct"),
            "mitigation_amount": cost.get("mitigation_amount") or 0,
            "prior_payment_amount": cost.get("prior_payment_amount") or 0,
            "cost_evidence_refs": list(cost.get("evidence_refs") or []),
            "causality_evidence_refs": list(cost.get("causality_evidence_refs") or []),
        })

    notice_flags = [x for x in analysis.get("flags", []) if x.startswith("NOTICE_")]
    if "NOTICE_ON_TIME" in notice_flags:
        notice_state = "ON_TIME"
    elif any(x in notice_flags for x in ("NOTICE_MISSED", "NOTICE_EXPIRED")):
        notice_state = "MISSED_OR_EXPIRED"
    elif "NOTICE_NOT_SENT_AT_RISK" in notice_flags:
        notice_state = "AT_RISK"
    elif "NOTICE_PROOF_MISSING" in notice_flags:
        notice_state = "PROOF_MISSING"
    elif entitlement.get("notice_required") is False:
        notice_state = "NOT_REQUIRED"
    else:
        notice_state = "UNKNOWN"

    identity = recovery_identity(case)
    return {
        "package_type": "ENGINEERING_CHANGE_RECOVERABILITY_REVIEW",
        "change_record_key": identity["change_record_key"],
        "technical_delta_key": identity["technical_delta_key"],
        "assisted_human_review_required": True,
        "engineering_change_summary": {
            "change_id": case.get("change_id"),
            "customer": case.get("customer"),
            "program": case.get("program"),
            "part": case.get("part"),
            "description": case.get("change_description"),
            "revision_from": case.get("revision_from"),
            "revision_to": case.get("revision_to"),
        },
        "before_after_delta": {
            "before": case.get("before_state") or {"revision": case.get("revision_from")},
            "after": case.get("after_state") or {"revision": case.get("revision_to")},
        },
        "affected_items": list(case.get("affected_items") or ([case.get("part")] if case.get("part") else [])),
        "cost_impact": cost_impact,
        "causality_analysis": [
            {"cost_id": item.get("id"), "causal_state": item.get("causal_state") or "UNKNOWN", "evidence_refs": list(item.get("causality_evidence_refs") or [])}
            for item in costs
        ],
        "mitigation": {
            "verified_amount": analysis.get("mitigated_amount", 0),
            "prior_payment_amount": analysis.get("prior_payment_amount", 0),
        },
        "commercial_basis": {
            "contract_state": entitlement.get("contract_state") or "UNKNOWN",
            "basis_evidence_refs": list(entitlement.get("basis_evidence_refs") or []),
            "prior_approval_required": entitlement.get("prior_approval_required"),
            "prior_approval_obtained": entitlement.get("prior_approval_obtained"),
        },
        "notice": {
            "state": notice_state,
            "required": entitlement.get("notice_required"),
            "deadline": entitlement.get("notice_deadline"),
            "sent": entitlement.get("notice_sent"),
            "evidence_refs": list(entitlement.get("notice_evidence_refs") or []),
        },
        "economic_outcome": {
            "currency": analysis.get("currency"),
            "verified_cost": analysis.get("cost_verified"),
            "recoverable_amount": analysis.get("recoverable_amount"),
            "nonrecoverable_amount": analysis.get("nonrecoverable_amount"),
            "unknown_amount": analysis.get("unknown_amount"),
            "status": analysis.get("status"),
        },
        "evidence": [
            {"id": item.get("id"), "type": item.get("type"), "verified": item.get("verified") is True,
             "superseded": item.get("superseded") is True, "asserts": item.get("asserts") or {}}
            for item in evidence
        ],
        "evidence_graph": analysis.get("evidence_graph") or {"nodes": [], "edges": []},
        "missing_evidence": list(analysis.get("missing_evidence") or []),
        "next_actions": list(analysis.get("next_actions") or []),
        "audit_trail": [{
            "event": "ANALYSIS_GENERATED",
            "analysis_date": analysis.get("analysis_date"),
            "input_sha256": _canonical_hash(case),
            "status": analysis.get("status"),
        }],
    }
