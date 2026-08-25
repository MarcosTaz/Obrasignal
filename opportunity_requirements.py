"""Traceable, conservative opportunity requirements extraction for ObraSignal.

V0 intentionally accepts already-structured opportunity/source fields and parsed
text. It does not perform OCR, call an LLM, verify registries, or implement
Opportunity Unlock. Unknown information stays unknown.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
from typing import Any, Iterable, Literal, Mapping, Sequence

RequirementCategory = Literal[
    "LEGAL", "FINANCIAL", "TECHNICAL", "EXPERIENCE", "CERTIFICATION",
    "INSURANCE", "GUARANTEE", "WORKFORCE", "EQUIPMENT", "REGISTRATION",
    "GEOGRAPHY", "DOCUMENT", "CONSORTIUM", "OTHER",
]
RequirementPriority = Literal["MANDATORY", "OPTIONAL", "PREFERRED", "UNKNOWN"]
Confidence = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
RequirementStatus = Literal["CURRENT", "SUPERSEDED", "CONFLICT", "CANDIDATE"]
EligibilityStatus = Literal["MET", "NOT_MET", "UNKNOWN", "NOT_EVALUATED"]

CATEGORIES = {
    "LEGAL", "FINANCIAL", "TECHNICAL", "EXPERIENCE", "CERTIFICATION",
    "INSURANCE", "GUARANTEE", "WORKFORCE", "EQUIPMENT", "REGISTRATION",
    "GEOGRAPHY", "DOCUMENT", "CONSORTIUM", "OTHER",
}
CONFIDENCES = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}

_CATEGORY_ALIASES = {
    "financial": "FINANCIAL", "turnover": "FINANCIAL", "revenue": "FINANCIAL",
    "certification": "CERTIFICATION", "certificate": "CERTIFICATION",
    "experience": "EXPERIENCE", "reference": "EXPERIENCE", "references": "EXPERIENCE",
    "insurance": "INSURANCE", "guarantee": "GUARANTEE", "bond": "GUARANTEE",
    "workforce": "WORKFORCE", "staff": "WORKFORCE", "personnel": "WORKFORCE",
    "equipment": "EQUIPMENT", "registration": "REGISTRATION", "licence": "REGISTRATION",
    "license": "REGISTRATION", "geography": "GEOGRAPHY", "location": "GEOGRAPHY",
    "document": "DOCUMENT", "documents": "DOCUMENT", "consortium": "CONSORTIUM",
    "legal": "LEGAL", "technical": "TECHNICAL",
}

_CURRENCY_ALIASES = {
    "€": "EUR", "EUR": "EUR", "EURO": "EUR", "EUROS": "EUR",
    "$": "USD", "USD": "USD", "US$": "USD", "GBP": "GBP", "£": "GBP",
    "CAD": "CAD", "C$": "CAD",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).casefold()).strip()


def _stable_id(*parts: Any) -> str:
    payload = "|".join(_norm_token(p) for p in parts)
    return "req_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True)
class RequirementEvidence:
    source_ref: str
    locator: str
    extraction_method: str = "structured"
    raw_value: str | None = None
    source_version: str | None = None
    document_id: str | None = None
    observed_at: str | None = None

    def identity(self) -> tuple[str, str, str | None]:
        return (self.source_ref, self.locator, self.source_version)


@dataclass(frozen=True)
class OpportunityRequirement:
    requirement_id: str
    opportunity_id: str
    category: RequirementCategory
    requirement_type: str
    description: str
    priority: RequirementPriority = "UNKNOWN"
    operator: str | None = None
    required_value: Any = None
    unit: str | None = None
    currency: str | None = None
    jurisdiction: str | None = None
    period: str | None = None
    evidence: tuple[RequirementEvidence, ...] = ()
    confidence: Confidence = "UNKNOWN"
    status: RequirementStatus = "CURRENT"
    supersedes: str | None = None
    extracted_at: str = field(default_factory=_utc_now)
    extractor_version: str = "requirements-v0.1"
    normalization_version: str = "requirements-normalization-v0.1"

    @property
    def mandatory(self) -> bool | None:
        if self.priority == "MANDATORY":
            return True
        if self.priority in {"OPTIONAL", "PREFERRED"}:
            return False
        return None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["mandatory"] = self.mandatory
        return data


@dataclass(frozen=True)
class RequirementAssessment:
    requirement: OpportunityRequirement
    eligibility: EligibilityStatus
    reason: str
    known_blocker: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement.to_dict(),
            "eligibility": self.eligibility,
            "reason": self.reason,
            "known_blocker": self.known_blocker,
        }


@dataclass(frozen=True)
class OpportunityRequirementsChecklist:
    opportunity_id: str
    requirements: tuple[OpportunityRequirement, ...]
    assessments: tuple[RequirementAssessment, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "requirements": [r.to_dict() for r in self.requirements],
            "assessments": [a.to_dict() for a in self.assessments],
            "summary": {
                "total": len(self.requirements),
                "mandatory": sum(r.priority == "MANDATORY" for r in self.requirements),
                "optional": sum(r.priority == "OPTIONAL" for r in self.requirements),
                "preferred": sum(r.priority == "PREFERRED" for r in self.requirements),
                "unknown_priority": sum(r.priority == "UNKNOWN" for r in self.requirements),
                "conflicts": sum(r.status == "CONFLICT" for r in self.requirements),
                "known_blockers": sum(a.known_blocker for a in self.assessments),
                "unknown_assessments": sum(a.eligibility == "UNKNOWN" for a in self.assessments),
            },
        }


def normalize_currency(value: Any) -> str | None:
    token = _clean(value).upper()
    return _CURRENCY_ALIASES.get(token)


def normalize_number(value: Any) -> Decimal | None:
    """Normalize explicit numeric values without guessing semantic units.

    Handles decimal/thousands separators plus explicit k/million suffixes. The
    raw source form is always preserved separately in RequirementEvidence.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Decimal(str(value))
    token = _clean(value)
    if not token:
        return None
    token = token.replace("\u00a0", " ")
    multiplier = Decimal("1")
    suffix = re.search(r"(?i)(?:\b(million|thousand)\b|(?<=\d)\s*([mk])\b)", token)
    if suffix:
        suffix_value = (suffix.group(1) or suffix.group(2) or "").lower()
        multiplier = Decimal("1000000") if suffix_value in {"million", "m"} else Decimal("1000")
    numeric = re.sub(r"[^0-9,.-]", "", token)
    if not numeric:
        return None
    if numeric.count(",") > 1 and "." not in numeric:
        numeric = numeric.replace(",", "")
    elif numeric.count(".") > 1 and "," not in numeric:
        numeric = numeric.replace(".", "")
    elif numeric.count(",") == 1 and "." not in numeric:
        tail = numeric.rsplit(",", 1)[1]
        numeric = numeric.replace(",", ".") if len(tail) <= 2 else numeric.replace(",", "")
    elif numeric.count(".") == 1 and "," not in numeric:
        tail = numeric.rsplit(".", 1)[1]
        if len(tail) == 3:
            numeric = numeric.replace(".", "")
    elif "," in numeric and "." in numeric:
        if numeric.rfind(",") > numeric.rfind("."):
            numeric = numeric.replace(".", "").replace(",", ".")
        else:
            numeric = numeric.replace(",", "")
    try:
        return Decimal(numeric) * multiplier
    except InvalidOperation:
        return None


def _priority(value: Any) -> RequirementPriority:
    if value is True:
        return "MANDATORY"
    if value is False:
        return "OPTIONAL"
    token = _norm_token(value)
    if token in {"mandatory", "required", "must", "shall", "true"}:
        return "MANDATORY"
    if token in {"optional", "false"}:
        return "OPTIONAL"
    if token in {"preferred", "desirable"}:
        return "PREFERRED"
    return "UNKNOWN"


def _category(value: Any, requirement_type: Any = None) -> RequirementCategory:
    token = _norm_token(value or requirement_type)
    if token.upper() in CATEGORIES:
        return token.upper()  # type: ignore[return-value]
    for alias, category in _CATEGORY_ALIASES.items():
        if alias in token:
            return category  # type: ignore[return-value]
    return "OTHER"


def _confidence(method: str, explicit: bool = True) -> Confidence:
    if method == "structured" and explicit:
        return "HIGH"
    if method == "text_rule" and explicit:
        return "MEDIUM"
    return "LOW"


def _make_requirement(
    *, opportunity_id: str, category: str, requirement_type: str, description: str,
    priority: Any = "UNKNOWN", operator: str | None = None, required_value: Any = None,
    unit: str | None = None, currency: str | None = None, jurisdiction: str | None = None,
    period: str | None = None, evidence: RequirementEvidence, confidence: str | None = None,
    status: RequirementStatus = "CURRENT", supersedes: str | None = None,
) -> OpportunityRequirement:
    category_n = _category(category, requirement_type)
    priority_n = _priority(priority)
    currency_n = normalize_currency(currency) or (_clean(currency).upper() or None)
    normalized_value = required_value
    if required_value is not None and (currency_n or unit in {"count", "years", "percent"}):
        parsed = normalize_number(required_value)
        if parsed is not None:
            normalized_value = int(parsed) if parsed == parsed.to_integral() else float(parsed)
    description_n = _clean(description)
    identity_value = normalized_value if normalized_value is not None else description_n
    req_id = _stable_id(opportunity_id, category_n, requirement_type, operator, identity_value, unit, currency_n, period, jurisdiction)
    return OpportunityRequirement(
        requirement_id=req_id,
        opportunity_id=str(opportunity_id),
        category=category_n,
        requirement_type=_clean(requirement_type) or "other",
        description=description_n,
        priority=priority_n,
        operator=_clean(operator) or None,
        required_value=normalized_value,
        unit=_clean(unit) or None,
        currency=currency_n,
        jurisdiction=_clean(jurisdiction) or None,
        period=_clean(period) or None,
        evidence=(evidence,),
        confidence=(confidence if confidence in CONFIDENCES else _confidence(evidence.extraction_method)),  # type: ignore[arg-type]
        status=status,
        supersedes=supersedes,
    )


class StructuredRequirementExtractor:
    """Extract explicit requirements from normalized source fields.

    Accepted inputs deliberately stay generic: `requirements` may be a list of
    dictionaries, while common explicit scalar/list fields are mapped without
    assuming country-specific semantics.
    """
    version = "structured-v0.1"

    FIELD_MAP = {
        "minimum_turnover": ("FINANCIAL", "minimum_turnover", ">=", None),
        "required_certifications": ("CERTIFICATION", "certification", None, None),
        "minimum_experience_years": ("EXPERIENCE", "years_experience", ">=", "years"),
        "insurance_requirements": ("INSURANCE", "insurance", None, None),
        "guarantee_requirements": ("GUARANTEE", "guarantee", None, None),
        "workforce_requirements": ("WORKFORCE", "workforce", None, None),
        "equipment_requirements": ("EQUIPMENT", "equipment", None, None),
        "registration_requirements": ("REGISTRATION", "registration", None, None),
        "document_requirements": ("DOCUMENT", "document", None, None),
        "geographical_requirements": ("GEOGRAPHY", "geography", None, None),
        "consortium_conditions": ("CONSORTIUM", "consortium", None, None),
    }

    def extract(self, source_context: Mapping[str, Any]) -> list[OpportunityRequirement]:
        opportunity_id = _clean(source_context.get("opportunity_id") or source_context.get("external_id"))
        if not opportunity_id:
            raise ValueError("opportunity_id or external_id is required")
        source_ref = _clean(source_context.get("source_ref") or source_context.get("source") or "unknown-source")
        source_version = _clean(source_context.get("source_version") or source_context.get("source_updated_at")) or None
        jurisdiction = _clean(source_context.get("jurisdiction") or source_context.get("country")) or None
        out: list[OpportunityRequirement] = []

        explicit = source_context.get("requirements")
        if isinstance(explicit, Sequence) and not isinstance(explicit, (str, bytes)):
            for idx, item in enumerate(explicit):
                if not isinstance(item, Mapping):
                    continue
                description = _clean(item.get("description") or item.get("raw_value") or item.get("value"))
                if not description:
                    continue
                raw = _clean(item.get("raw_value") or item.get("value") or description)
                evidence = RequirementEvidence(
                    source_ref=source_ref,
                    locator=_clean(item.get("locator") or f"requirements[{idx}]"),
                    extraction_method="structured",
                    raw_value=raw,
                    source_version=source_version,
                    document_id=_clean(item.get("document_id")) or None,
                )
                out.append(_make_requirement(
                    opportunity_id=opportunity_id,
                    category=_clean(item.get("category")),
                    requirement_type=_clean(item.get("requirement_type") or item.get("type") or item.get("category") or "other"),
                    description=description,
                    priority=item.get("priority", item.get("mandatory", "UNKNOWN")),
                    operator=_clean(item.get("operator")) or None,
                    required_value=item.get("required_value", item.get("value")),
                    unit=_clean(item.get("unit")) or None,
                    currency=_clean(item.get("currency")) or None,
                    jurisdiction=_clean(item.get("jurisdiction")) or jurisdiction,
                    period=_clean(item.get("period")) or None,
                    evidence=evidence,
                    confidence=_clean(item.get("confidence")).upper() or None,
                    status=_clean(item.get("status")).upper() if _clean(item.get("status")).upper() in {"CURRENT", "SUPERSEDED", "CONFLICT", "CANDIDATE"} else "CURRENT",
                    supersedes=_clean(item.get("supersedes")) or None,
                ))

        for field_name, (category, req_type, operator, unit) in self.FIELD_MAP.items():
            value = source_context.get(field_name)
            if value in (None, "", [], {}):
                continue
            values = value if isinstance(value, list) else [value]
            for idx, raw_value in enumerate(values):
                if isinstance(raw_value, Mapping):
                    item = raw_value
                    raw = _clean(item.get("raw_value") or item.get("value") or item.get("description"))
                    description = _clean(item.get("description") or raw)
                    req_value = item.get("required_value", item.get("value"))
                    curr = _clean(item.get("currency")) or _clean(source_context.get("currency")) or None
                    priority = item.get("priority", item.get("mandatory", "MANDATORY"))
                    item_operator = _clean(item.get("operator")) or operator
                    item_unit = _clean(item.get("unit")) or unit
                    item_period = _clean(item.get("period")) or None
                else:
                    raw = _clean(raw_value)
                    description = raw
                    req_value = raw_value
                    curr = _clean(source_context.get("currency")) or None
                    priority = "MANDATORY"
                    item_operator, item_unit, item_period = operator, unit, None
                evidence = RequirementEvidence(
                    source_ref=source_ref,
                    locator=f"field:{field_name}" + (f"[{idx}]" if len(values) > 1 else ""),
                    extraction_method="structured",
                    raw_value=raw,
                    source_version=source_version,
                )
                out.append(_make_requirement(
                    opportunity_id=opportunity_id, category=category, requirement_type=req_type,
                    description=description, priority=priority, operator=item_operator,
                    required_value=req_value, unit=item_unit, currency=curr,
                    jurisdiction=jurisdiction, period=item_period, evidence=evidence,
                ))
        return consolidate_requirements(out)


class ConservativeTextRequirementExtractor:
    """Small explicit-rule extractor for already parsed text.

    It deliberately ignores mere mentions. A sentence must contain bidder-facing
    obligation language. Negative statements are rejected.
    """
    version = "text-rules-v0.1"
    _obligation = re.compile(r"\b(bidder|tenderer|applicant|contractor|supplier)\b.{0,80}\b(must|shall|required to|is required to|are required to)\b", re.I)
    _negative = re.compile(r"\b(not required|need not|isn't required|is not mandatory|optional)\b", re.I)
    _cert = re.compile(r"\bISO\s*\d{4,5}(?:\s*:\s*\d{4})?\b", re.I)

    def extract(self, source_context: Mapping[str, Any]) -> list[OpportunityRequirement]:
        opportunity_id = _clean(source_context.get("opportunity_id") or source_context.get("external_id"))
        text = _clean(source_context.get("normalized_text") or source_context.get("text"))
        if not opportunity_id or not text:
            return []
        source_ref = _clean(source_context.get("source_ref") or source_context.get("source") or "unknown-source")
        source_version = _clean(source_context.get("source_version") or source_context.get("source_updated_at")) or None
        results: list[OpportunityRequirement] = []
        sentences = re.split(r"(?<=[.!?;])\s+", text)
        for idx, sentence in enumerate(sentences):
            if self._negative.search(sentence) or not self._obligation.search(sentence):
                continue
            cert = self._cert.search(sentence)
            if not cert:
                continue
            evidence = RequirementEvidence(
                source_ref=source_ref, locator=f"normalized_text:sentence:{idx + 1}",
                extraction_method="text_rule", raw_value=sentence, source_version=source_version,
                document_id=_clean(source_context.get("document_id")) or None,
            )
            results.append(_make_requirement(
                opportunity_id=opportunity_id, category="CERTIFICATION", requirement_type="certification",
                description=sentence, priority="MANDATORY", required_value=cert.group(0),
                jurisdiction=_clean(source_context.get("jurisdiction") or source_context.get("country")) or None,
                evidence=evidence, confidence="MEDIUM",
            ))
        return consolidate_requirements(results)


def _semantic_key(req: OpportunityRequirement) -> tuple[Any, ...]:
    return (
        req.opportunity_id, req.category, _norm_token(req.requirement_type), req.operator,
        _norm_token(req.required_value), _norm_token(req.unit), _norm_token(req.currency),
        _norm_token(req.period), _norm_token(req.jurisdiction), req.priority,
    )


def consolidate_requirements(requirements: Iterable[OpportunityRequirement]) -> list[OpportunityRequirement]:
    """Safely deduplicate exact-equivalent requirements and surface conflicts."""
    by_key: dict[tuple[Any, ...], OpportunityRequirement] = {}
    for req in requirements:
        key = _semantic_key(req)
        current = by_key.get(key)
        if current is None:
            by_key[key] = req
            continue
        evidences = {e.identity(): e for e in (*current.evidence, *req.evidence)}
        by_key[key] = replace(current, evidence=tuple(evidences.values()), confidence="HIGH" if "HIGH" in {current.confidence, req.confidence} else current.confidence)

    items = list(by_key.values())
    groups: dict[tuple[Any, ...], list[int]] = {}
    for idx, req in enumerate(items):
        conflict_key = (req.opportunity_id, req.category, _norm_token(req.requirement_type), _norm_token(req.period), _norm_token(req.jurisdiction), req.priority)
        groups.setdefault(conflict_key, []).append(idx)
    for indices in groups.values():
        values = {(items[i].operator, _norm_token(items[i].required_value), _norm_token(items[i].unit), _norm_token(items[i].currency)) for i in indices}
        if len(indices) > 1 and len(values) > 1:
            for i in indices:
                if items[i].status == "CURRENT":
                    items[i] = replace(items[i], status="CONFLICT")
    return sorted(items, key=lambda r: (r.category, r.requirement_type, r.requirement_id))


def supersede(requirements: Iterable[OpportunityRequirement], old_id: str, new_id: str) -> list[OpportunityRequirement]:
    ids = {r.requirement_id for r in requirements}
    if old_id not in ids or new_id not in ids:
        raise KeyError("both old_id and new_id must exist")
    return [replace(r, status="SUPERSEDED") if r.requirement_id == old_id else replace(r, supersedes=old_id) if r.requirement_id == new_id else r for r in requirements]


def build_checklist(source_context: Mapping[str, Any], *, include_text_rules: bool = True) -> OpportunityRequirementsChecklist:
    opportunity_id = _clean(source_context.get("opportunity_id") or source_context.get("external_id"))
    structured = StructuredRequirementExtractor().extract(source_context)
    text = ConservativeTextRequirementExtractor().extract(source_context) if include_text_rules else []
    return OpportunityRequirementsChecklist(opportunity_id=opportunity_id, requirements=tuple(consolidate_requirements([*structured, *text])))


def assess_against_company(requirement: OpportunityRequirement, company_profile: Mapping[str, Any] | None) -> RequirementAssessment:
    """Conservative comparison against facts that the current profile actually carries.

    V0 evaluates certifications only. Other categories remain NOT_EVALUATED rather
    than pretending the existing profile is a Company State contract.
    """
    if not company_profile:
        return RequirementAssessment(requirement, "UNKNOWN", "Company data unavailable.")
    if requirement.category != "CERTIFICATION":
        return RequirementAssessment(requirement, "NOT_EVALUATED", "Current company profile has no defensible comparable fact for this requirement type.")
    known = company_profile.get("certifications")
    if known is None:
        return RequirementAssessment(requirement, "UNKNOWN", "Certification data is missing from company profile.")
    known_tokens = {_norm_token(value) for value in (known or []) if _clean(value)}
    required = _norm_token(requirement.required_value or requirement.description)
    if not known_tokens:
        return RequirementAssessment(requirement, "UNKNOWN", "No certification facts are recorded; absence is not evidence of non-compliance.")
    if any(required == token or (required and required in token) for token in known_tokens):
        return RequirementAssessment(requirement, "MET", "Recorded company certification matches the explicit requirement.")
    return RequirementAssessment(requirement, "UNKNOWN", "Recorded certifications do not prove this requirement is unmet.")


def assess_checklist(checklist: OpportunityRequirementsChecklist, company_profile: Mapping[str, Any] | None, *, account_id: str | None = None) -> OpportunityRequirementsChecklist:
    if company_profile is not None and account_id is not None:
        profile_account = _clean(company_profile.get("account_id"))
        if profile_account and profile_account != _clean(account_id):
            raise PermissionError("company profile account does not match assessment account")
    assessments = tuple(assess_against_company(r, company_profile) for r in checklist.requirements)
    return replace(checklist, assessments=assessments)
