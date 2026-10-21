"""Public integration between Opportunity Requirements and Company State v1.

This module owns comparison glue only. Requirements owns what the opportunity
requires. Company State owns what is known about the company. This adapter never
creates company facts, edits requirements, or makes a pursuit decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Any, Iterable, Mapping

from company_state import CompanyState, TenantBoundaryError
from company_state_adapters import requirements_facts

RESULT_STATES = frozenset({
    "MET", "NOT_MET", "UNKNOWN", "NOT_EVALUATED", "CONFLICT", "NOT_APPLICABLE",
})
NEGATIVE_STATUSES = frozenset({"NOT_HELD", "NOT_CERTIFIED", "EXPIRED", "REVOKED", "INVALID", "UNAVAILABLE"})
POSITIVE_STATUSES = frozenset({"HELD", "VALID", "CURRENT", "AVAILABLE", "OPERATING", "YES", "TRUE"})


@dataclass(frozen=True)
class RequirementComparison:
    requirement_id: str
    status: str
    reason: str
    mandatory: bool
    requirement_source_refs: tuple[str, ...] = ()
    company_fact_ids: tuple[str, ...] = ()
    company_evidence_refs: tuple[str, ...] = ()
    company_provenance_bases: tuple[str, ...] = ()
    company_state_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.status not in RESULT_STATES:
            raise ValueError(f"unsupported requirement comparison state: {self.status}")

    def to_readiness_dict(self, requirement: Any) -> dict[str, Any]:
        evidence_refs = tuple(dict.fromkeys((*self.requirement_source_refs, *self.company_evidence_refs)))
        return {
            "code": self.requirement_id,
            "name": getattr(requirement, "description", None) or getattr(requirement, "requirement_type", None) or "requirement",
            "mandatory": self.mandatory,
            "status": self.status,
            "reason": self.reason,
            "source_ref": self.requirement_source_refs[0].split("#", 1)[0] if self.requirement_source_refs else None,
            "evidence_ref": evidence_refs[0] if evidence_refs else None,
            "evidence_refs": list(evidence_refs),
            "company_fact_ids": list(self.company_fact_ids),
            "company_provenance_bases": list(self.company_provenance_bases),
            "company_state_fingerprint": self.company_state_fingerprint,
        }


def _token(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _requirement_refs(requirement: Any) -> tuple[str, ...]:
    refs: list[str] = []
    for evidence in tuple(getattr(requirement, "evidence", ()) or ()):
        source = str(getattr(evidence, "source_ref", "") or "").strip()
        locator = str(getattr(evidence, "locator", "") or "").strip()
        ref = f"{source}#{locator}" if source and locator else source
        if ref:
            refs.append(ref)
    return tuple(dict.fromkeys(refs))


def _mandatory(requirement: Any) -> bool:
    priority = str(getattr(requirement, "priority", "UNKNOWN") or "UNKNOWN").upper()
    return priority not in {"OPTIONAL", "PREFERRED"}


def _fact_text(fact: Mapping[str, Any]) -> str:
    parts = [fact.get("code"), fact.get("scope")]
    value = fact.get("value")
    if isinstance(value, Mapping):
        parts.extend(value.values())
    elif isinstance(value, (list, tuple)):
        parts.extend(value)
    else:
        parts.append(value)
    return _token(" ".join(str(item) for item in parts if item not in (None, "")))


def _matching_token_fact(facts: Iterable[Mapping[str, Any]], token: str, *, categories: set[str]) -> list[Mapping[str, Any]]:
    if not token:
        return []
    compact = token.replace(" ", "")
    result = []
    for fact in facts:
        if str(fact.get("category") or "") not in categories:
            continue
        text = _fact_text(fact)
        if token in text or compact in text.replace(" ", ""):
            result.append(fact)
    return result


def _fact_refs(facts: Iterable[Mapping[str, Any]]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    ids: list[str] = []
    evidence: list[str] = []
    bases: list[str] = []
    for fact in facts:
        fact_id = str(fact.get("fact_id") or "").strip()
        if fact_id:
            ids.append(fact_id)
        provenance = fact.get("provenance") or {}
        if isinstance(provenance, Mapping):
            ev = str(provenance.get("evidence_ref") or provenance.get("source_ref") or "").strip()
            if ev:
                evidence.append(ev)
            basis = str(provenance.get("basis") or "").strip()
            if basis:
                bases.append(basis)
    return tuple(sorted(set(ids))), tuple(sorted(set(evidence))), tuple(sorted(set(bases)))


def _conflicting(envelope: Mapping[str, Any], facts: Iterable[Mapping[str, Any]]) -> bool:
    ids = {str(f.get("fact_id") or "") for f in facts}
    codes = {str(f.get("code") or "") for f in facts}
    for conflict in envelope.get("conflicts") or ():
        if not isinstance(conflict, Mapping):
            continue
        if str(conflict.get("code") or "") in codes:
            return True
        if ids.intersection(str(item) for item in (conflict.get("fact_ids") or ())):
            return True
    return False


def _result(requirement: Any, envelope: Mapping[str, Any] | None, status: str, reason: str,
            facts: Iterable[Mapping[str, Any]] = ()) -> RequirementComparison:
    facts = tuple(facts)
    ids, evidence, bases = _fact_refs(facts)
    return RequirementComparison(
        requirement_id=str(getattr(requirement, "requirement_id", "") or "requirement"),
        status=status,
        reason=reason,
        mandatory=_mandatory(requirement),
        requirement_source_refs=_requirement_refs(requirement),
        company_fact_ids=ids,
        company_evidence_refs=evidence,
        company_provenance_bases=bases,
        company_state_fingerprint=str((envelope or {}).get("company_state_fingerprint") or "") or None,
    )


def _known_current(fact: Mapping[str, Any]) -> bool:
    return str(fact.get("knowledge") or "") != "UNKNOWN" and str(fact.get("freshness") or "") not in {"STALE", "EXPIRED", "NOT_YET_EFFECTIVE"}


def _explicit_negative(fact: Mapping[str, Any]) -> bool:
    value = fact.get("value")
    if value is False:
        return True
    if isinstance(value, Mapping):
        tokens = {
            str(value.get("status") or "").upper(),
            str(value.get("validity") or "").upper(),
            str(value.get("availability") or "").upper(),
        }
        return bool(tokens & NEGATIVE_STATUSES)
    return str(value or "").upper() in NEGATIVE_STATUSES


def _certification(requirement: Any, envelope: Mapping[str, Any]) -> RequirementComparison:
    required = _token(getattr(requirement, "required_value", None) or getattr(requirement, "description", ""))
    active = _matching_token_fact(envelope.get("facts") or (), required, categories={"QUALIFICATION"})
    non_current = _matching_token_fact(envelope.get("non_current_facts") or (), required, categories={"QUALIFICATION"})
    all_matches = (*active, *non_current)
    if _conflicting(envelope, active):
        return _result(requirement, envelope, "CONFLICT", "Current company certification facts conflict.", active)
    expired = [fact for fact in non_current if str(fact.get("freshness") or "") == "EXPIRED" and str(fact.get("knowledge") or "") != "UNKNOWN"]
    if expired:
        return _result(requirement, envelope, "NOT_MET", "Matching certification is explicitly expired.", expired)
    if not active:
        return _result(requirement, envelope, "UNKNOWN", "No matching certification fact is recorded; absence is not non-certification.", all_matches)
    if any(
        str(f.get("knowledge") or "") == "UNKNOWN"
        or str(f.get("freshness") or "") in {"STALE", "UNKNOWN"}
        for f in active
    ):
        return _result(requirement, envelope, "UNKNOWN", "Matching certification exists but its current validity/state or freshness is not established.", active)
    if any(_explicit_negative(f) for f in active):
        return _result(requirement, envelope, "NOT_MET", "Matching current certification fact explicitly records non-compliance.", active)
    for fact in active:
        value = fact.get("value")
        if isinstance(value, Mapping) and str(value.get("validity") or "").upper() == "UNKNOWN":
            return _result(requirement, envelope, "UNKNOWN", "Certification is recorded as held but current validity is unknown.", active)
    if active and all(_known_current(f) for f in active):
        return _result(requirement, envelope, "MET", "A current matching certification fact satisfies the requirement.", active)
    return _result(requirement, envelope, "UNKNOWN", "Certification comparison is not sufficiently current.", active)


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, Decimal)):
        return Decimal(str(value))
    if isinstance(value, float):
        return Decimal(str(value))
    text = str(value or "")
    match = re.search(r"(?<!\d)(\d+(?:[.,]\d+)?)", text)
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        return None


def _single_code(envelope: Mapping[str, Any], code: str) -> list[Mapping[str, Any]]:
    return [fact for fact in (envelope.get("facts") or ()) if str(fact.get("code") or "") == code]


def _minimum_workforce_semantics(requirement: Any) -> bool:
    operator = str(getattr(requirement, "operator", "") or "").strip().casefold()
    if operator:
        return operator in {">=", "=>", "at_least", "at least", "minimum", "min"}
    description = _token(getattr(requirement, "description", ""))
    return "at least" in description or "minimum" in description or description.startswith("min ")


def _workforce(requirement: Any, envelope: Mapping[str, Any]) -> RequirementComparison:
    required = _number(getattr(requirement, "required_value", None))
    if required is None:
        required = _number(getattr(requirement, "description", ""))
    if required is None:
        return _result(requirement, envelope, "NOT_EVALUATED", "Workforce requirement has no defensible numeric available-crew threshold.")
    if not _minimum_workforce_semantics(requirement):
        return _result(requirement, envelope, "NOT_EVALUATED", "Workforce comparison only supports an explicit minimum/at-least available-crew requirement.")
    facts = _single_code(envelope, "crew.available_count")
    if _conflicting(envelope, facts):
        return _result(requirement, envelope, "CONFLICT", "Available-crew facts conflict.", facts)
    if not facts:
        return _result(requirement, envelope, "UNKNOWN", "Available crew is not recorded; total headcount is not availability.")
    if any(str(f.get("knowledge") or "") == "UNKNOWN" or str(f.get("freshness") or "") in {"STALE", "UNKNOWN"} for f in facts):
        return _result(requirement, envelope, "UNKNOWN", "Available crew is unknown or not current.", facts)
    values = [_number(f.get("value")) for f in facts if _known_current(f)]
    values = [value for value in values if value is not None]
    if len(set(values)) != 1:
        return _result(requirement, envelope, "CONFLICT", "Available-crew facts do not resolve to one value.", facts)
    if not values:
        return _result(requirement, envelope, "UNKNOWN", "Available crew cannot be compared.", facts)
    status = "MET" if values[0] >= required else "NOT_MET"
    reason = "Known available crew meets the explicit minimum requirement." if status == "MET" else "Known available crew is below the explicit minimum requirement."
    return _result(requirement, envelope, status, reason, facts)


def _country_tokens(value: Any) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        return {_token(item).upper().replace(" ", "") for item in value if _token(item)}
    token = _token(value).upper().replace(" ", "")
    return {token} if token else set()


def _geography(requirement: Any, envelope: Mapping[str, Any]) -> RequirementComparison:
    required = _country_tokens(getattr(requirement, "required_value", None) or getattr(requirement, "description", ""))
    if not required:
        return _result(requirement, envelope, "NOT_EVALUATED", "Geography requirement cannot be normalized conservatively.")
    facts = _single_code(envelope, "geography.operating_countries")
    if _conflicting(envelope, facts):
        return _result(requirement, envelope, "CONFLICT", "Operational-geography facts conflict.", facts)
    if not facts:
        return _result(requirement, envelope, "UNKNOWN", "Operational countries are unknown; preferred geography is not eligibility.")
    if any(str(f.get("knowledge") or "") == "UNKNOWN" or str(f.get("freshness") or "") == "STALE" for f in facts):
        return _result(requirement, envelope, "UNKNOWN", "Operational geography is unknown or stale.", facts)
    countries: set[str] = set()
    for fact in facts:
        countries |= _country_tokens(fact.get("value"))
    if not countries:
        return _result(requirement, envelope, "UNKNOWN", "Operational geography has no usable country values.", facts)
    if required & countries:
        return _result(requirement, envelope, "MET", "Known operational geography includes the required country.", facts)
    return _result(requirement, envelope, "NOT_MET", "Known operational geography excludes the required country.", facts)


def _presence(requirement: Any, envelope: Mapping[str, Any], *, categories: set[str]) -> RequirementComparison:
    required_raw = getattr(requirement, "required_value", None) or getattr(requirement, "description", "")
    required = _token(required_raw)
    matches = _matching_token_fact(envelope.get("facts") or (), required, categories=categories)
    if _conflicting(envelope, matches):
        return _result(requirement, envelope, "CONFLICT", "Comparable company facts conflict.", matches)
    if not matches:
        return _result(requirement, envelope, "UNKNOWN", "No matching company fact is recorded; absence is not a negative fact.")
    if any(str(f.get("knowledge") or "") == "UNKNOWN" or str(f.get("freshness") or "") == "STALE" for f in matches):
        return _result(requirement, envelope, "UNKNOWN", "Matching company fact is unknown or stale.", matches)
    if any(_explicit_negative(f) for f in matches):
        return _result(requirement, envelope, "NOT_MET", "Matching company fact explicitly records non-compliance.", matches)
    return _result(requirement, envelope, "MET", "A matching known company fact satisfies the requirement.", matches)


def compare_requirement(requirement: Any, company_state: CompanyState | None, *, account_id: str) -> RequirementComparison:
    status = str(getattr(requirement, "status", "CURRENT") or "CURRENT").upper()
    if status == "SUPERSEDED":
        return _result(requirement, None, "NOT_APPLICABLE", "Superseded requirement is not evaluated as current.")
    if status == "CONFLICT":
        return _result(requirement, None, "CONFLICT", "Opportunity requirement sources conflict.")
    if status == "CANDIDATE":
        return _result(requirement, None, "NOT_EVALUATED", "Candidate requirement is not authoritative enough for eligibility.")
    if company_state is None:
        return _result(requirement, None, "UNKNOWN", "Company State is unavailable.")
    if company_state.account_id != str(account_id or "").strip():
        raise TenantBoundaryError("company state belongs to a different account")

    envelope = requirements_facts(company_state)
    category = str(getattr(requirement, "category", "OTHER") or "OTHER").upper()
    if category == "CERTIFICATION":
        return _certification(requirement, envelope)
    if category == "WORKFORCE":
        return _workforce(requirement, envelope)
    if category == "GEOGRAPHY":
        return _geography(requirement, envelope)
    if category == "EQUIPMENT":
        return _presence(requirement, envelope, categories={"EQUIPMENT"})
    if category == "TECHNICAL":
        return _presence(requirement, envelope, categories={"CAPABILITY"})
    return _result(
        requirement,
        envelope,
        "NOT_EVALUATED",
        f"Company State v1 has no defensible public comparison rule for {category}.",
    )


def compare_checklist(checklist: Any, company_state: CompanyState | None, *, account_id: str) -> tuple[RequirementComparison, ...]:
    return tuple(
        compare_requirement(requirement, company_state, account_id=account_id)
        for requirement in tuple(getattr(checklist, "requirements", ()) or ())
    )
