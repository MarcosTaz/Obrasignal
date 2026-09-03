"""Truth-preserving aggregate metrics for customer decision intelligence.

Metrics in this module are observational read models only. They never turn the
absence of review, usefulness, decision, or outcome evidence into zero and they
never mutate ranking, filters, ICP, decisions, or owner state.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

CRITICAL_INPUTS = frozenset({"source_truth", "evidence", "company_state", "readiness", "economics"})
DEGRADED_STATES = frozenset({"UNKNOWN", "STALE", "UNAVAILABLE", "CONFLICTED"})
EXPLICIT_DECISIONS = frozenset({"PURSUE", "NO_BID", "HOLD", "NEEDS_INFO"})
OBSERVED_OUTCOMES = frozenset({"BID_SUBMITTED", "WON", "LOST", "WITHDRAWN", "NO_SUBMISSION", "CANCELLED"})


def _ratio(numerator: int, denominator: int, *, reason_if_empty: str) -> dict[str, Any]:
    if denominator <= 0:
        return {
            "state": "UNAVAILABLE",
            "numerator": numerator,
            "denominator": denominator,
            "rate": None,
            "reason": reason_if_empty,
        }
    return {
        "state": "KNOWN",
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator,
        "reason": None,
    }


def _explicit_metric_unavailable(reason: str) -> dict[str, Any]:
    return {
        "state": "UNAVAILABLE",
        "numerator": None,
        "denominator": None,
        "rate": None,
        "reason": reason,
    }


def _inputs_by_name(audit: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("name")): item
        for item in (audit.get("inputs") or [])
        if isinstance(item, Mapping) and item.get("name")
    }


def decision_metrics(audits: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate only what the audit contracts actually prove.

    The function deliberately refuses to manufacture review/usefulness rates.
    An audit is not proof that a customer reviewed an opportunity, and a PURSUE
    decision is not proof that the opportunity was useful or good.

    A valid/KNOWN owner envelope may still expose explicit unknown sub-inputs.
    Those unknowns count as decision-data exposure without falsifying the
    envelope's own truth-state classification.
    """
    rows = list(audits)
    seen_identity: set[tuple[str, str, str]] = set()
    explicit_decisions = 0
    decision_counts: dict[str, int] = defaultdict(int)
    observed_outcomes = 0
    outcome_eligible = 0
    degraded_decisions = 0
    stale_decisions = 0
    critical_slots = 0
    degraded_slots = 0
    unknown_exposure_slots = 0
    explicit_unknown_subinputs = 0
    envelope_unknown_slots = 0
    stale_slots = 0
    unavailable_slots = 0
    conflicted_slots = 0

    for audit in rows:
        if not isinstance(audit, Mapping):
            raise TypeError("audits must contain mapping values")
        account = str(audit.get("account_id") or "").strip()
        opportunity = audit.get("opportunity") or {}
        if not isinstance(opportunity, Mapping):
            raise ValueError("audit opportunity must be a mapping")
        source = str(opportunity.get("source") or "").strip()
        external_id = str(opportunity.get("external_id") or "").strip()
        if not account or not source or not external_id:
            raise ValueError("decision metric audit requires account/source/external_id")
        identity = (account, source, external_id)
        if identity in seen_identity:
            raise ValueError("decision metrics require one current audit per tenant/opportunity")
        seen_identity.add(identity)

        inputs = _inputs_by_name(audit)
        degraded_for_decision = False
        stale_for_decision = False
        for name in CRITICAL_INPUTS:
            critical_slots += 1
            item = inputs.get(name)
            state = str(item.get("truth_state") if item else "UNAVAILABLE").strip().upper()
            raw_unknowns = item.get("unknowns") if item else ()
            if isinstance(raw_unknowns, (str, bytes)):
                raw_unknowns = (raw_unknowns,)
            explicit_unknowns = [value for value in (raw_unknowns or ()) if str(value).strip()]
            has_explicit_unknowns = bool(explicit_unknowns)
            explicit_unknown_subinputs += len(explicit_unknowns)

            if state in DEGRADED_STATES or has_explicit_unknowns:
                degraded_slots += 1
                degraded_for_decision = True
            if state == "UNKNOWN" or has_explicit_unknowns:
                unknown_exposure_slots += 1
            if state == "UNKNOWN":
                envelope_unknown_slots += 1
            elif state == "STALE":
                stale_slots += 1
                stale_for_decision = True
            elif state == "UNAVAILABLE":
                unavailable_slots += 1
            elif state == "CONFLICTED":
                conflicted_slots += 1

        decision = str(audit.get("explicit_pursuit_decision") or "").strip().upper()
        if decision in EXPLICIT_DECISIONS:
            explicit_decisions += 1
            decision_counts[decision] += 1
            outcome_eligible += 1
            if degraded_for_decision:
                degraded_decisions += 1
            if stale_for_decision:
                stale_decisions += 1

            outcome = str(audit.get("current_outcome") or "").strip().upper()
            if outcome in OBSERVED_OUTCOMES:
                observed_outcomes += 1

    return {
        "contract_version": "customer-decision-metrics.v1",
        "audited_opportunities": len(rows),
        "explicit_decisions": explicit_decisions,
        "decision_counts": dict(sorted(decision_counts.items())),
        "unknown_data_rate": _ratio(
            unknown_exposure_slots,
            critical_slots,
            reason_if_empty="no critical decision-input slots were observed",
        ),
        "degraded_input_rate": _ratio(
            degraded_slots,
            critical_slots,
            reason_if_empty="no critical decision-input slots were observed",
        ),
        "stale_decision_exposure": _ratio(
            stale_decisions,
            explicit_decisions,
            reason_if_empty="no explicit pursuit decisions were observed",
        ),
        "degraded_decision_exposure": _ratio(
            degraded_decisions,
            explicit_decisions,
            reason_if_empty="no explicit pursuit decisions were observed",
        ),
        "outcome_capture_completeness": _ratio(
            observed_outcomes,
            outcome_eligible,
            reason_if_empty="no explicit pursuit decisions are eligible for outcome capture",
        ),
        "truth_state_counts": {
            "UNKNOWN": envelope_unknown_slots,
            "STALE": stale_slots,
            "UNAVAILABLE": unavailable_slots,
            "CONFLICTED": conflicted_slots,
        },
        "explicit_unknown_subinputs": explicit_unknown_subinputs,
        "unknown_exposure_slots": unknown_exposure_slots,
        # These require explicit product telemetry/labels not present in the
        # decision audit contract. Returning 0 would be false intelligence.
        "useful_opportunities_surfaced": _explicit_metric_unavailable(
            "customer usefulness observation is not present in the audit contract"
        ),
        "review_to_pursuit": _explicit_metric_unavailable(
            "review event evidence is not present in the audit contract"
        ),
        "review_to_decline": _explicit_metric_unavailable(
            "review event evidence is not present in the audit contract"
        ),
        "decision_reversal_rate": _explicit_metric_unavailable(
            "one current audit per opportunity cannot prove historical decision reversals"
        ),
        "optimization_allowed": False,
    }
