"""Deterministic, conservative bid-readiness assessment for ObraSignal.

Readiness answers whether an account has enough verified information to proceed
with bid preparation. It is deliberately not a BID/NO-BID decision engine.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from typing import Any, Iterable

ASSESSMENT_VERSION = "opportunity-readiness.v0"
POLICY_VERSION = "opportunity-readiness-policy.v0"
CLOSED_LIFECYCLE_STATES = {"CLOSED", "CANCELLED", "CANCELED", "AWARDED", "EXPIRED", "COMPLETED"}


@dataclass(frozen=True)
class ReadinessItem:
    code: str
    dimension: str
    description: str
    severity: str
    status: str
    critical: bool
    source_ref: str | None = None
    evidence_ref: str | None = None


class TenantBoundaryError(ValueError):
    pass


def _now_utc(clock: datetime | None) -> datetime:
    value = clock or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_deadline(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, 23, 59, 59, tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _explicit_bool(value: Any) -> bool | None:
    """Normalize explicit publisher/SQLite booleans without truthiness guessing."""
    if value is True or value == 1:
        return True
    if value is False or value == 0:
        return False
    if isinstance(value, str):
        token = value.strip().casefold()
        if token in {"true", "1"}:
            return True
        if token in {"false", "0"}:
            return False
    return None


def _source_ref(opportunity: dict[str, Any]) -> str | None:
    source = str(opportunity.get("source") or "").strip()
    external = str(opportunity.get("external_id") or "").strip()
    return f"{source}:{external}" if source and external else source or external or None


def _item(code: str, dimension: str, description: str, severity: str, status: str,
          critical: bool, source_ref: str | None = None, evidence_ref: str | None = None) -> ReadinessItem:
    return ReadinessItem(code, dimension, description, severity, status, critical, source_ref, evidence_ref)


def _requirement_items(requirements: Iterable[dict[str, Any]] | None, source_ref: str | None):
    if requirements is None:
        return [
            _item(
                "eligibility_requirements_unavailable", "ELIGIBILITY",
                "Mandatory eligibility requirements have not been verified for this opportunity.",
                "VERIFY", "UNKNOWN", True, source_ref,
            )
        ]
    results: list[ReadinessItem] = []
    seen = False
    for raw in requirements:
        if not isinstance(raw, dict):
            continue
        seen = True
        # Only an explicit False makes a requirement non-mandatory. Unknown or
        # omitted priority must stay conservative rather than becoming optional
        # through bool(None) coercion.
        mandatory = raw.get("mandatory", True) is not False
        status = str(raw.get("status") or "UNKNOWN").strip().upper()
        name = str(raw.get("name") or raw.get("code") or "requirement").strip()
        evidence_ref = raw.get("evidence_ref")
        requirement_source = raw.get("source_ref") or source_ref
        if status in {"MET", "READY", "SATISFIED"}:
            results.append(_item("requirement_met", "ELIGIBILITY", f"Requirement verified: {name}.", "INFO", "READY", mandatory, requirement_source, evidence_ref))
        elif status in {"NOT_MET", "BLOCKED", "FAILED"} and mandatory:
            results.append(_item("mandatory_requirement_not_met", "ELIGIBILITY", f"Mandatory requirement not met: {name}.", "BLOCKER", "BLOCKED", True, requirement_source, evidence_ref))
        elif status in {"NOT_MET", "BLOCKED", "FAILED"}:
            results.append(_item("optional_requirement_not_met", "ELIGIBILITY", f"Optional requirement not met: {name}.", "WARNING", "WARNING", False, requirement_source, evidence_ref))
        else:
            results.append(_item("requirement_unknown", "ELIGIBILITY", f"Requirement still unverified: {name}.", "VERIFY", "UNKNOWN", mandatory, requirement_source, evidence_ref))
    if not seen:
        results.append(_item("eligibility_no_mandatory_requirements_reported", "ELIGIBILITY", "No eligibility blockers are reported by the supplied requirements contract.", "INFO", "READY", True, source_ref))
    return results


def _economic_item(result: dict[str, Any] | None, source_ref: str | None) -> list[ReadinessItem]:
    if not result:
        return [_item("economic_fit_unavailable", "FINANCIAL", "Economic fit could not be evaluated from current data.", "VERIFY", "UNKNOWN", False, source_ref)]
    status = str(result.get("status") or "UNKNOWN").upper()
    evidence = result.get("rule_version")
    reason = str(result.get("reason") or "Economic fit assessment available.")
    if status == "FAVOURABLE":
        return [_item("economic_fit_favourable", "FINANCIAL", reason, "INFO", "READY", False, source_ref, evidence)]
    if status == "UNFAVOURABLE":
        return [_item("economic_fit_unfavourable", "FINANCIAL", reason, "WARNING", "WARNING", False, source_ref, evidence)]
    return [_item("economic_fit_unknown", "FINANCIAL", reason, "VERIFY", "UNKNOWN", False, source_ref, evidence)]


def _dimension_status(items: list[ReadinessItem]) -> str:
    statuses = {item.status for item in items}
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    if "WARNING" in statuses:
        return "WARNING"
    if "READY" in statuses:
        return "READY"
    return "NOT_APPLICABLE"


def evaluate_readiness(
    account_id: str,
    opportunity: dict[str, Any],
    company_state: dict[str, Any] | None = None,
    *,
    requirements: Iterable[dict[str, Any]] | None = None,
    economic_fit_result: dict[str, Any] | None = None,
    clock: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate readiness using only explicit inputs and deterministic rules.

    ``company_state`` may only describe ``account_id``. Missing information is
    UNKNOWN, never an implicit pass. Same inputs + same clock + same policy
    produce the same result.
    """
    account = str(account_id or "").strip()
    if not account:
        raise TenantBoundaryError("account_id is required")
    company_state = company_state or {}
    company_account = str(company_state.get("account_id") or account).strip()
    if company_account != account:
        raise TenantBoundaryError("company_state belongs to a different account")

    now = _now_utc(clock)
    source_ref = _source_ref(opportunity)
    items: list[ReadinessItem] = []

    lifecycle = str(opportunity.get("lifecycle_status") or "").strip().upper()
    actionable = _explicit_bool(opportunity.get("is_actionable"))
    if actionable is False or lifecycle in CLOSED_LIFECYCLE_STATES:
        label = lifecycle or "NOT_ACTIONABLE"
        items.append(_item("opportunity_not_actionable", "OPPORTUNITY_STATUS", f"Opportunity is not actionable ({label}).", "BLOCKER", "BLOCKED", True, source_ref, opportunity.get("lifecycle_source_updated_at")))
    elif actionable is True or lifecycle in {"OPEN", "ACTIVE", "PUBLISHED"}:
        items.append(_item("opportunity_actionable", "OPPORTUNITY_STATUS", "Opportunity is currently reported as actionable.", "INFO", "READY", True, source_ref, opportunity.get("lifecycle_source_updated_at")))
    else:
        items.append(_item("opportunity_status_unknown", "OPPORTUNITY_STATUS", "Current opportunity lifecycle status is not explicitly verified.", "VERIFY", "UNKNOWN", True, source_ref))

    deadline_raw = opportunity.get("deadline")
    deadline = _parse_deadline(deadline_raw)
    if deadline_raw in (None, ""):
        items.append(_item("submission_deadline_missing", "DEADLINE", "Official submission deadline is not available.", "VERIFY", "UNKNOWN", True, source_ref))
    elif deadline is None:
        items.append(_item("submission_deadline_invalid", "DEADLINE", "Official submission deadline could not be parsed and must be verified.", "VERIFY", "UNKNOWN", True, source_ref))
    elif deadline.astimezone(timezone.utc) <= now:
        items.append(_item("submission_deadline_expired", "DEADLINE", "Official submission deadline has passed or is now due.", "BLOCKER", "BLOCKED", True, source_ref))
    else:
        remaining_hours = (deadline.astimezone(timezone.utc) - now).total_seconds() / 3600
        items.append(_item("submission_deadline_valid", "DEADLINE", "Official submission deadline is still open.", "INFO", "READY", True, source_ref))
        if remaining_hours <= 48:
            items.append(_item("submission_deadline_near", "DEADLINE", "Official submission deadline is within 48 hours; preparation time is constrained.", "WARNING", "WARNING", False, source_ref))

    items.extend(_requirement_items(requirements, source_ref))

    economic_result = economic_fit_result
    if economic_result is None:
        try:
            from economic_fit import evaluate_economic_fit
            economic_result = evaluate_economic_fit(
                opportunity.get("value"), company_state, opportunity, today=now.date()
            )
        except Exception:
            economic_result = None
    items.extend(_economic_item(economic_result, source_ref))

    if not opportunity.get("source") or not opportunity.get("external_id"):
        items.append(_item("source_identity_incomplete", "SOURCE_COMPLETENESS", "Source identity is incomplete and should be verified before relying on this assessment.", "VERIFY", "UNKNOWN", False, source_ref))
    else:
        items.append(_item("source_identity_known", "SOURCE_COMPLETENESS", "Source and external opportunity identity are known.", "INFO", "READY", False, source_ref))

    blocking = [item for item in items if item.status == "BLOCKED"]
    warnings = [item for item in items if item.status == "WARNING"]
    unknowns = [item for item in items if item.status == "UNKNOWN"]
    ready = [item for item in items if item.status == "READY"]
    critical_unknowns = [item for item in unknowns if item.critical]

    if blocking:
        overall = "NOT_READY"
    elif critical_unknowns:
        overall = "UNKNOWN"
    elif warnings or unknowns:
        overall = "CONDITIONALLY_READY"
    else:
        overall = "READY"

    dimensions: dict[str, dict[str, Any]] = {}
    for dimension in sorted({item.dimension for item in items}):
        dimension_items = [item for item in items if item.dimension == dimension]
        dimensions[dimension] = {
            "status": _dimension_status(dimension_items),
            "items": [asdict(item) for item in dimension_items],
        }

    known = len(items) - len(unknowns)
    completeness = round((known / len(items)) * 100) if items else 0
    evidence_refs = sorted({str(item.evidence_ref) for item in items if item.evidence_ref})
    next_checks = [item.description for item in unknowns] + [item.description for item in warnings]

    return {
        "opportunity_id": opportunity.get("id") or opportunity.get("external_id"),
        "account_id": account,
        "overall_status": overall,
        "dimensions": dimensions,
        "blocking_items": [asdict(item) for item in blocking],
        "warning_items": [asdict(item) for item in warnings],
        "unknown_items": [asdict(item) for item in unknowns],
        "ready_items": [asdict(item) for item in ready],
        "generated_at": now.isoformat(),
        "assessment_version": ASSESSMENT_VERSION,
        "policy_version": POLICY_VERSION,
        "evidence_refs": evidence_refs,
        "data_completeness_percent": completeness,
        "next_checks": next_checks,
    }
