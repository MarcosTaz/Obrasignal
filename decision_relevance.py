"""Explicit company-relevance semantics orthogonal to action decisions.

`decision` answers what the product should do next. Relevance answers what the
available company-specific evidence actually establishes. Consumers must never
infer relevance from QUALIFIED/REVIEW/REJECT labels.
"""
from __future__ import annotations

RELEVANCE_RULE_VERSION = "relevance-v1"
RELEVANT = "RELEVANT"
NOT_RELEVANT = "NOT_RELEVANT"
UNKNOWN = "UNKNOWN"
RELEVANCE_STATES = frozenset({RELEVANT, NOT_RELEVANT, UNKNOWN})


def derive_relevance(capability_evidence, cpv_evidence, hard_blockers):
    """Return bounded, versioned relevance evidence without coercing missing data.

    Positive company-specific service/capability evidence or a sufficiently
    specific CPV prefix proves RELEVANT. Explicit CPV exclusion or a configured
    hard exclusion can prove NOT_RELEVANT. Everything else remains UNKNOWN.

    A relevant opportunity may still have timing/economic/procedure/geographic
    blockers; those affect shortlist eligibility, not the relevance fact itself.
    """
    capability_evidence = capability_evidence if isinstance(capability_evidence, dict) else {}
    cpv_evidence = cpv_evidence if isinstance(cpv_evidence, dict) else {}
    blockers = [str(value) for value in (hard_blockers or [])]

    evidence = []
    for value in capability_evidence.get("matched_services", []) or []:
        evidence.append({"kind": "service", "value": str(value)})
    for value in capability_evidence.get("matched_capabilities", []) or []:
        evidence.append({"kind": "capability", "value": str(value)})
    if cpv_evidence.get("strength") == "STRONG":
        for value in cpv_evidence.get("matched_prefixes", []) or []:
            evidence.append({"kind": "cpv_prefix", "value": str(value)})

    if evidence:
        state = RELEVANT
    elif any(
        blocker == "CPV fora das famílias aceites pela empresa"
        or blocker.startswith("exclusão da empresa encontrada:")
        for blocker in blockers
    ):
        state = NOT_RELEVANT
        evidence = [{"kind": "explicit_profile_conflict"}]
    else:
        state = UNKNOWN

    return {
        "state": state,
        "evidence": evidence,
        "rule_version": RELEVANCE_RULE_VERSION,
    }


def relevance_state_from_features(features, *, expected_rule_version=RELEVANCE_RULE_VERSION):
    """Read current relevance from persisted decision features, fail-closed.

    Historical rows, malformed payloads and rows created under superseded
    relevance semantics are UNKNOWN. REVIEW is never used as a fallback.
    """
    if not isinstance(features, dict):
        return UNKNOWN
    relevance = features.get("relevance")
    if not isinstance(relevance, dict):
        return UNKNOWN
    if relevance.get("rule_version") != expected_rule_version:
        return UNKNOWN
    state = relevance.get("state")
    return state if state in RELEVANCE_STATES else UNKNOWN


def relevant_shortlist_eligible_from_features(features, *, expected_rule_version=RELEVANCE_RULE_VERSION):
    """Return explicit relevance eligibility only for current relevance semantics.

    Decision freshness (rule/profile authority) is a separate upstream contract
    and must also be proven by consumers before this result authorizes current
    customer-facing effects.
    """
    if relevance_state_from_features(
        features,
        expected_rule_version=expected_rule_version,
    ) != RELEVANT:
        return False
    return features.get("relevant_shortlist_eligible") is True
