"""Experiment and verified-learning contracts for ObraSignal.

The module validates semantics only. It intentionally does not create a persistent
learning database; retention/deletion/export requirements for new analytics storage
remain an Account/Privacy + Data Reliability boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone

LEARNING_VERSION = "analytics-learning-v1"
LEARNING_STATES = frozenset({"PROVEN", "SIGNAL", "ASSUMPTION", "DISPROVEN", "UNKNOWN"})


def _non_empty(value):
    return bool(str(value or "").strip())


def _iso(value):
    if not _non_empty(value):
        raise ValueError("timestamp_required")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def experiment_contract(*, hypothesis, population, primary_metric, guardrails,
                        duration, decision_rule, owner, exclusions=None):
    """Create a falsifiable experiment contract before results are inspected."""
    required = {
        "hypothesis": hypothesis,
        "population": population,
        "primary_metric": primary_metric,
        "duration": duration,
        "decision_rule": decision_rule,
        "owner": owner,
    }
    missing = [name for name, value in required.items() if not _non_empty(value)]
    if missing:
        raise ValueError({"incomplete_experiment_contract": missing})
    if not isinstance(guardrails, (list, tuple)) or not guardrails:
        raise ValueError("experiment_guardrails_required")
    normalized_guardrails = [str(item).strip() for item in guardrails if _non_empty(item)]
    if not normalized_guardrails:
        raise ValueError("experiment_guardrails_required")
    lowered = " ".join(normalized_guardrails).lower()
    if "truth" not in lowered or ("security" not in lowered and "privacy" not in lowered):
        raise ValueError("experiment_must_guard_product_truth_and_security_or_privacy")

    return {
        "schema_version": LEARNING_VERSION,
        "hypothesis": str(hypothesis).strip(),
        "population": str(population).strip(),
        "primary_metric": str(primary_metric).strip(),
        "guardrails": normalized_guardrails,
        "duration": str(duration).strip(),
        "decision_rule": str(decision_rule).strip(),
        "owner": str(owner).strip(),
        "exclusions": [str(item).strip() for item in (exclusions or []) if _non_empty(item)],
        "causality_claim": "NOT_ESTABLISHED_UNTIL_EXPERIMENT_DESIGN_AND_EVIDENCE_SUPPORT_IT",
        "dark_patterns": "FORBIDDEN",
        "security_or_truth_weakening": "FORBIDDEN",
    }


def learning_record(*, state, claim, observed_at, source_owner, decision_use,
                    evidence_refs=None, review_at=None):
    """Create one evidence-labelled learning record.

    PROVEN/DISPROVEN/SIGNAL require explicit evidence references. ASSUMPTION and
    UNKNOWN may exist without evidence, but remain visibly non-proven.
    """
    state = str(state or "").upper().strip()
    if state not in LEARNING_STATES:
        raise ValueError("invalid_learning_state")
    for name, value in {
        "claim": claim,
        "source_owner": source_owner,
        "decision_use": decision_use,
    }.items():
        if not _non_empty(value):
            raise ValueError(f"learning_{name}_required")

    evidence = [str(ref).strip() for ref in (evidence_refs or []) if _non_empty(ref)]
    if state in {"PROVEN", "DISPROVEN", "SIGNAL"} and not evidence:
        raise ValueError(f"{state.lower()}_learning_requires_evidence")

    observed = _iso(observed_at)
    review = _iso(review_at) if review_at is not None else None
    if review and review < observed:
        raise ValueError("learning_review_before_observation")

    return {
        "schema_version": LEARNING_VERSION,
        "state": state,
        "claim": str(claim).strip(),
        "evidence_refs": evidence,
        "observed_at": observed,
        "source_owner": str(source_owner).strip(),
        "decision_use": str(decision_use).strip(),
        "review_at": review,
        "causality": "NOT_CLAIMED" if state != "PROVEN" else "REQUIRES_SEPARATE_CAUSAL_EVIDENCE",
    }


def is_learning_stale(record, *, now=None):
    """Return True only when an explicit review boundary has elapsed."""
    review_at = (record or {}).get("review_at")
    if not review_at:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    review = datetime.fromisoformat(str(review_at).replace("Z", "+00:00"))
    if review.tzinfo is None:
        review = review.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc) >= review.astimezone(timezone.utc)
