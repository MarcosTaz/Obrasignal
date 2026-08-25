"""Deterministic, conservative operational bid-readiness assessment for ObraSignal.

Readiness summarizes preparation state. It never owns PURSUE/NO_BID and never
turns partial extraction, missing company facts, or imprecise time into certainty.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
import re
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ASSESSMENT_VERSION = "opportunity-readiness.v0.2"
POLICY_VERSION = "opportunity-readiness-policy.v0.2"
CLOSED_LIFECYCLE_STATES = {"CLOSED", "CANCELLED", "CANCELED", "AWARDED", "EXPIRED", "COMPLETED"}
TEMPORAL_PRECISIONS = {"DATE", "MONTH", "QUARTER", "YEAR", "DATETIME", "UNKNOWN"}
EVIDENCE_CONTRACT = {
    "status": "UNAVAILABLE",
    "contract": "evidence-graph.v1",
    "reason": "Q080 public Evidence contract is not present on this integration base.",
}


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
    evidence_refs: tuple[str, ...] = ()
    requirement_status: str | None = None
    requirement_id: str | None = None
    company_fact_ids: tuple[str, ...] = ()
    temporal_precision: str | None = None
    timezone_status: str | None = None


@dataclass(frozen=True)
class ParsedDeadline:
    precision: str
    instant: datetime | None
    timezone_status: str
    raw: Any


class TenantBoundaryError(ValueError):
    pass


def _now_utc(clock: datetime | None) -> datetime:
    value = clock or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError("readiness clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def _localize_naive(value: datetime, timezone_name: str | None) -> tuple[datetime | None, str]:
    name = str(timezone_name or "").strip()
    if not name:
        return None, "UNKNOWN"
    try:
        zone = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None, "UNKNOWN"
    return value.replace(tzinfo=zone).astimezone(timezone.utc), "KNOWN"


def _parse_deadline(value: Any, *, precision_hint: Any = None, timezone_name: Any = None) -> ParsedDeadline | None:
    if value in (None, ""):
        return None

    hint = str(precision_hint or "").strip().upper()
    if hint and hint not in TEMPORAL_PRECISIONS:
        hint = "UNKNOWN"

    if isinstance(value, datetime):
        if hint in {"DATE", "MONTH", "QUARTER", "YEAR", "UNKNOWN"}:
            return ParsedDeadline(hint, None, "UNKNOWN", value)
        if value.tzinfo is not None:
            return ParsedDeadline("DATETIME", value.astimezone(timezone.utc), "KNOWN", value)
        instant, tz_status = _localize_naive(value, str(timezone_name or ""))
        return ParsedDeadline("DATETIME", instant, tz_status, value)

    if isinstance(value, date):
        return ParsedDeadline("DATE", None, "UNKNOWN", value)

    text = str(value).strip()
    if not text:
        return None

    if re.fullmatch(r"\d{4}", text):
        return ParsedDeadline("YEAR", None, "UNKNOWN", value)
    if re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", text):
        return ParsedDeadline("MONTH", None, "UNKNOWN", value)
    if re.fullmatch(r"\d{4}-Q[1-4]", text, re.I) or re.fullmatch(r"Q[1-4][ -]?\d{4}", text, re.I):
        return ParsedDeadline("QUARTER", None, "UNKNOWN", value)
    if re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])", text):
        return ParsedDeadline("DATE", None, "UNKNOWN", value)

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ParsedDeadline("UNKNOWN", None, "UNKNOWN", value)

    if hint in {"DATE", "MONTH", "QUARTER", "YEAR", "UNKNOWN"}:
        return ParsedDeadline(hint, None, "UNKNOWN", value)
    if parsed.tzinfo is not None:
        return ParsedDeadline("DATETIME", parsed.astimezone(timezone.utc), "KNOWN", value)
    instant, tz_status = _localize_naive(parsed, str(timezone_name or ""))
    return ParsedDeadline("DATETIME", instant, tz_status, value)


def _explicit_bool(value: Any) -> bool | None:
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
          critical: bool, source_ref: str | None = None, evidence_ref: str | None = None,
          *, evidence_refs: Iterable[str] = (), requirement_status: str | None = None,
          requirement_id: str | None = None, company_fact_ids: Iterable[str] = (),
          temporal_precision: str | None = None, timezone_status: str | None = None) -> ReadinessItem:
    refs = tuple(dict.fromkeys(
        str(value).strip()
        for value in ((evidence_ref,) if evidence_ref else ()) + tuple(evidence_refs or ())
        if str(value).strip()
    ))
    return ReadinessItem(
        code, dimension, description, severity, status, critical, source_ref,
        evidence_ref or (refs[0] if refs else None), refs, requirement_status,
        requirement_id, tuple(dict.fromkeys(str(v) for v in company_fact_ids if str(v))),
        temporal_precision, timezone_status,
    )


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
        mandatory = raw.get("mandatory", True) is not False
        requirement_status = str(raw.get("status") or "UNKNOWN").strip().upper()
        name = str(raw.get("name") or raw.get("code") or "requirement").strip()
        evidence_ref = raw.get("evidence_ref")
        evidence_refs = raw.get("evidence_refs") or ()
        requirement_source = raw.get("source_ref") or source_ref
        requirement_id = str(raw.get("code") or "").strip() or None
        company_fact_ids = raw.get("company_fact_ids") or ()
        reason = str(raw.get("reason") or "").strip()

        if requirement_status in {"MET", "READY", "SATISFIED"}:
            results.append(_item(
                "requirement_met", "ELIGIBILITY",
                reason or f"Requirement verified: {name}.",
                "INFO", "READY", mandatory, requirement_source, evidence_ref,
                evidence_refs=evidence_refs, requirement_status="MET",
                requirement_id=requirement_id, company_fact_ids=company_fact_ids,
            ))
        elif requirement_status in {"NOT_MET", "BLOCKED", "FAILED"} and mandatory:
            results.append(_item(
                "mandatory_requirement_not_met", "ELIGIBILITY",
                reason or f"Mandatory requirement not met: {name}.",
                "BLOCKER", "BLOCKED", True, requirement_source, evidence_ref,
                evidence_refs=evidence_refs, requirement_status="NOT_MET",
                requirement_id=requirement_id, company_fact_ids=company_fact_ids,
            ))
        elif requirement_status in {"NOT_MET", "BLOCKED", "FAILED"}:
            results.append(_item(
                "optional_requirement_not_met", "ELIGIBILITY",
                reason or f"Optional requirement not met: {name}.",
                "WARNING", "WARNING", False, requirement_source, evidence_ref,
                evidence_refs=evidence_refs, requirement_status="NOT_MET",
                requirement_id=requirement_id, company_fact_ids=company_fact_ids,
            ))
        elif requirement_status == "CONFLICT":
            results.append(_item(
                "requirement_conflict", "ELIGIBILITY",
                reason or f"Requirement/company evidence conflicts: {name}.",
                "VERIFY", "CONFLICT", mandatory, requirement_source, evidence_ref,
                evidence_refs=evidence_refs, requirement_status="CONFLICT",
                requirement_id=requirement_id, company_fact_ids=company_fact_ids,
            ))
        elif requirement_status == "NOT_APPLICABLE":
            results.append(_item(
                "requirement_not_applicable", "ELIGIBILITY",
                reason or f"Requirement is not applicable: {name}.",
                "INFO", "NOT_APPLICABLE", False, requirement_source, evidence_ref,
                evidence_refs=evidence_refs, requirement_status="NOT_APPLICABLE",
                requirement_id=requirement_id, company_fact_ids=company_fact_ids,
            ))
        else:
            results.append(_item(
                "requirement_unknown", "ELIGIBILITY",
                reason or f"Requirement still unverified: {name}.",
                "VERIFY", "UNKNOWN", mandatory, requirement_source, evidence_ref,
                evidence_refs=evidence_refs,
                requirement_status="NOT_EVALUATED" if requirement_status == "NOT_EVALUATED" else "UNKNOWN",
                requirement_id=requirement_id, company_fact_ids=company_fact_ids,
            ))
    if not seen:
        results.append(_item(
            "eligibility_no_mandatory_requirements_reported", "ELIGIBILITY",
            "No eligibility blockers are reported by the supplied requirements contract.",
            "INFO", "READY", True, source_ref,
        ))
    return results


def _economic_item(result: dict[str, Any] | None, source_ref: str | None) -> list[ReadinessItem]:
    if not result:
        return [_item(
            "economic_fit_unavailable", "FINANCIAL",
            "Economic fit is unavailable; Readiness does not infer it from Company State.",
            "VERIFY", "UNKNOWN", False, source_ref,
        )]
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
    if "CONFLICT" in statuses:
        return "CONFLICT"
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
    """Evaluate readiness using explicit public inputs and deterministic rules."""
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
        items.append(_item(
            "opportunity_not_actionable", "OPPORTUNITY_STATUS",
            f"Opportunity is not actionable ({label}).", "BLOCKER", "BLOCKED", True,
            source_ref, opportunity.get("lifecycle_source_updated_at"),
        ))
    elif actionable is True or lifecycle in {"OPEN", "ACTIVE", "PUBLISHED"}:
        items.append(_item(
            "opportunity_actionable", "OPPORTUNITY_STATUS",
            "Opportunity is currently reported as actionable.", "INFO", "READY", True,
            source_ref, opportunity.get("lifecycle_source_updated_at"),
        ))
    else:
        items.append(_item(
            "opportunity_status_unknown", "OPPORTUNITY_STATUS",
            "Current opportunity lifecycle status is not explicitly verified.",
            "VERIFY", "UNKNOWN", True, source_ref,
        ))

    deadline_raw = opportunity.get("deadline")
    deadline = _parse_deadline(
        deadline_raw,
        precision_hint=opportunity.get("deadline_precision"),
        timezone_name=opportunity.get("deadline_timezone"),
    )
    if deadline is None:
        items.append(_item(
            "submission_deadline_missing", "DEADLINE",
            "Official submission deadline is not available.", "VERIFY", "UNKNOWN", True, source_ref,
            temporal_precision="UNKNOWN", timezone_status="UNKNOWN",
        ))
    elif deadline.precision != "DATETIME":
        items.append(_item(
            "submission_deadline_precision_insufficient", "DEADLINE",
            f"Submission deadline is known only to {deadline.precision} precision; no exact open/expired instant is inferred.",
            "VERIFY", "UNKNOWN", True, source_ref,
            temporal_precision=deadline.precision, timezone_status=deadline.timezone_status,
        ))
    elif deadline.instant is None:
        items.append(_item(
            "submission_deadline_timezone_unknown", "DEADLINE",
            "Submission deadline has time-of-day precision but no authoritative timezone.",
            "VERIFY", "UNKNOWN", True, source_ref,
            temporal_precision="DATETIME", timezone_status="UNKNOWN",
        ))
    elif deadline.instant <= now:
        items.append(_item(
            "submission_deadline_expired", "DEADLINE",
            "Official submission deadline has passed or is now due.", "BLOCKER", "BLOCKED", True,
            source_ref, temporal_precision="DATETIME", timezone_status="KNOWN",
        ))
    else:
        remaining_hours = (deadline.instant - now).total_seconds() / 3600
        items.append(_item(
            "submission_deadline_valid", "DEADLINE",
            "Official submission deadline is still open.", "INFO", "READY", True,
            source_ref, temporal_precision="DATETIME", timezone_status="KNOWN",
        ))
        if remaining_hours <= 48:
            items.append(_item(
                "submission_deadline_near", "DEADLINE",
                "Official submission deadline is within 48 hours; preparation time is constrained.",
                "WARNING", "WARNING", False, source_ref,
                temporal_precision="DATETIME", timezone_status="KNOWN",
            ))

    items.extend(_requirement_items(requirements, source_ref))
    items.extend(_economic_item(economic_fit_result, source_ref))

    company_status = str(company_state.get("status") or "").upper()
    if company_status == "UNAVAILABLE":
        items.append(_item(
            "company_state_unavailable", "COMPANY_STATE",
            "Canonical Company State could not be loaded; company-dependent readiness remains unknown.",
            "VERIFY", "UNKNOWN", True, source_ref,
        ))

    if not opportunity.get("source") or not opportunity.get("external_id"):
        items.append(_item(
            "source_identity_incomplete", "SOURCE_COMPLETENESS",
            "Source identity is incomplete and should be verified before relying on this assessment.",
            "VERIFY", "UNKNOWN", False, source_ref,
        ))
    else:
        items.append(_item(
            "source_identity_known", "SOURCE_COMPLETENESS",
            "Source and external opportunity identity are known.", "INFO", "READY", False, source_ref,
        ))

    blocking = [item for item in items if item.status == "BLOCKED"]
    warnings = [item for item in items if item.status == "WARNING"]
    conflicts = [item for item in items if item.status == "CONFLICT"]
    unknowns = [item for item in items if item.status == "UNKNOWN"]
    ready = [item for item in items if item.status == "READY"]
    critical_unknowns = [item for item in unknowns if item.critical]
    critical_conflicts = [item for item in conflicts if item.critical]

    if blocking:
        overall = "NOT_READY"
    elif critical_unknowns or critical_conflicts:
        overall = "UNKNOWN"
    elif warnings or unknowns or conflicts:
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

    unresolved = len(unknowns) + len(conflicts)
    known = len(items) - unresolved
    completeness = round((known / len(items)) * 100) if items else 0
    evidence_refs = sorted({
        ref
        for item in items
        for ref in ((item.evidence_ref,) + item.evidence_refs)
        if ref
    })
    next_checks = [item.description for item in unknowns] + [item.description for item in conflicts] + [item.description for item in warnings]

    return {
        "opportunity_id": opportunity.get("id") or opportunity.get("external_id"),
        "account_id": account,
        "overall_status": overall,
        "dimensions": dimensions,
        "blocking_items": [asdict(item) for item in blocking],
        "warning_items": [asdict(item) for item in warnings],
        "conflict_items": [asdict(item) for item in conflicts],
        "unknown_items": [asdict(item) for item in unknowns],
        "ready_items": [asdict(item) for item in ready],
        "generated_at": now.isoformat(),
        "assessment_version": ASSESSMENT_VERSION,
        "policy_version": POLICY_VERSION,
        "evidence_contract": dict(EVIDENCE_CONTRACT),
        "evidence_refs": evidence_refs,
        "data_completeness_percent": completeness,
        "next_checks": next_checks,
    }
