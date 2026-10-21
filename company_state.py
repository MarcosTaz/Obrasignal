"""Canonical Company Operational State v1 contract for ObraSignal.

This module models tenant-private facts about what a contractor is known to be
able to execute at a particular time. It intentionally does not decide
eligibility, readiness, bid economics, mobilisation, pursuit or external action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "company-state.v1"
FINGERPRINT_VERSION = "company-state-fingerprint.v1"
MAX_FACTS = 256
MAX_FACT_CODE = 96
MAX_TEXT = 1000
MAX_SOURCE_REF = 512
MAX_EVIDENCE_REF = 256
MAX_COLLECTION_ITEMS = 64
MAX_MAPPING_ITEMS = 64
MAX_VALUE_DEPTH = 5
MAX_SERIALIZED_VALUE_BYTES = 16_384
MAX_SNAPSHOT_BYTES = 262_144

_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_FACT_CODE_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,95}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class CompanyStateError(ValueError):
    """Base validation error for the public contract."""


class TenantBoundaryError(CompanyStateError):
    """Raised when data crosses a trusted account boundary."""


class KnowledgeState(str, Enum):
    FACT = "FACT"
    ASSUMPTION = "ASSUMPTION"
    ESTIMATE = "ESTIMATE"
    INFERENCE = "INFERENCE"
    UNKNOWN = "UNKNOWN"


class ProvenanceBasis(str, Enum):
    DECLARED = "DECLARED"
    PROFILE = "PROFILE"
    VERIFIED = "VERIFIED"
    PUBLIC_REGISTRY = "PUBLIC_REGISTRY"
    INTEGRATION = "INTEGRATION"
    LEARNED = "LEARNED"
    UNAVAILABLE = "UNAVAILABLE"


class FactCategory(str, Enum):
    CAPABILITY = "CAPABILITY"
    CAPACITY = "CAPACITY"
    AVAILABILITY = "AVAILABILITY"
    GEOGRAPHY = "GEOGRAPHY"
    EQUIPMENT = "EQUIPMENT"
    QUALIFICATION = "QUALIFICATION"
    FINANCIAL_CONSTRAINT = "FINANCIAL_CONSTRAINT"
    OPERATIONAL_CONSTRAINT = "OPERATIONAL_CONSTRAINT"


class FreshnessState(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    NOT_YET_EFFECTIVE = "NOT_YET_EFFECTIVE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        try:
            amount = self.amount if isinstance(self.amount, Decimal) else Decimal(str(self.amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise CompanyStateError("money amount must be a finite decimal") from exc
        if not amount.is_finite():
            raise CompanyStateError("money amount must be finite")
        currency = str(self.currency or "").strip().upper()
        if not _CURRENCY_RE.fullmatch(currency):
            raise CompanyStateError("money currency must be explicit ISO-like three-letter code")
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "currency", currency)

    def to_dict(self) -> dict[str, str]:
        return {"amount": format(self.amount, "f"), "currency": self.currency}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Money":
        if not isinstance(data, Mapping) or "amount" not in data or "currency" not in data:
            raise CompanyStateError("money requires amount and currency")
        return cls(data["amount"], str(data["currency"]))


@dataclass(frozen=True)
class Provenance:
    basis: ProvenanceBasis
    source_ref: str | None = None
    evidence_ref: str | None = None
    observed_at: datetime | None = None
    verified_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "basis", _enum(ProvenanceBasis, self.basis, "provenance basis"))
        object.__setattr__(self, "source_ref", _bounded_optional_text(self.source_ref, MAX_SOURCE_REF, "source_ref"))
        object.__setattr__(self, "evidence_ref", _bounded_optional_text(self.evidence_ref, MAX_EVIDENCE_REF, "evidence_ref"))
        object.__setattr__(self, "observed_at", _utc_optional(self.observed_at, "observed_at"))
        object.__setattr__(self, "verified_at", _utc_optional(self.verified_at, "verified_at"))
        if self.basis is ProvenanceBasis.VERIFIED and self.verified_at is None and not self.evidence_ref:
            raise CompanyStateError("VERIFIED provenance requires verified_at or evidence_ref")

    def to_dict(self) -> dict[str, Any]:
        return {
            "basis": self.basis.value,
            "source_ref": self.source_ref,
            "evidence_ref": self.evidence_ref,
            "observed_at": _iso(self.observed_at),
            "verified_at": _iso(self.verified_at),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Provenance":
        if not isinstance(data, Mapping):
            raise CompanyStateError("provenance must be an object")
        return cls(
            basis=data.get("basis", ProvenanceBasis.DECLARED),
            source_ref=data.get("source_ref"),
            evidence_ref=data.get("evidence_ref"),
            observed_at=_parse_dt(data.get("observed_at"), "observed_at"),
            verified_at=_parse_dt(data.get("verified_at"), "verified_at"),
        )


@dataclass(frozen=True)
class CompanyFact:
    category: FactCategory
    code: str
    knowledge: KnowledgeState
    value: Any = None
    provenance: Provenance = field(default_factory=lambda: Provenance(ProvenanceBasis.DECLARED))
    scope: str | None = None
    unit: str | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    freshness_until: datetime | None = None
    supersedes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "category", _enum(FactCategory, self.category, "fact category"))
        object.__setattr__(self, "knowledge", _enum(KnowledgeState, self.knowledge, "knowledge state"))
        code = str(self.code or "").strip()
        if not _FACT_CODE_RE.fullmatch(code):
            raise CompanyStateError("fact code is invalid")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "scope", _bounded_optional_text(self.scope, 128, "scope"))
        object.__setattr__(self, "unit", _bounded_optional_text(self.unit, 32, "unit"))
        effective_from = _utc_optional(self.effective_from, "effective_from")
        effective_until = _utc_optional(self.effective_until, "effective_until")
        freshness_until = _utc_optional(self.freshness_until, "freshness_until")
        if effective_from and effective_until and effective_from > effective_until:
            raise CompanyStateError("effective_from must be <= effective_until")
        object.__setattr__(self, "effective_from", effective_from)
        object.__setattr__(self, "effective_until", effective_until)
        object.__setattr__(self, "freshness_until", freshness_until)
        if not isinstance(self.provenance, Provenance):
            raise CompanyStateError("provenance must be Provenance")
        if self.provenance.basis is ProvenanceBasis.LEARNED and self.knowledge is not KnowledgeState.INFERENCE:
            raise CompanyStateError("LEARNED provenance must remain INFERENCE, never FACT")
        if self.knowledge is KnowledgeState.INFERENCE and self.provenance.basis is not ProvenanceBasis.LEARNED:
            raise CompanyStateError("INFERENCE knowledge requires LEARNED provenance")
        if self.provenance.basis is ProvenanceBasis.UNAVAILABLE and self.knowledge is not KnowledgeState.UNKNOWN:
            raise CompanyStateError("UNAVAILABLE provenance can only describe UNKNOWN data")
        supersedes = tuple(dict.fromkeys(str(item).strip() for item in self.supersedes if str(item).strip()))
        if len(supersedes) > 32:
            raise CompanyStateError("supersedes is too large")
        object.__setattr__(self, "supersedes", supersedes)
        if self.category is FactCategory.FINANCIAL_CONSTRAINT and self.code in {
            "finance.maximum_cash_exposure", "finance.working_capital_limit", "finance.guarantee_limit"
        } and self.knowledge is not KnowledgeState.UNKNOWN and not isinstance(self.value, Money):
            raise CompanyStateError("monetary financial constraints require Money with explicit currency")
        if isinstance(self.value, Money) and self.category is FactCategory.FINANCIAL_CONSTRAINT and self.value.amount < 0:
            raise CompanyStateError("financial constraint money cannot be negative")
        if self.knowledge is KnowledgeState.UNKNOWN:
            if self.value is not None:
                raise CompanyStateError("UNKNOWN fact must have null value")
        else:
            if self.value is None:
                raise CompanyStateError("known/assumed/estimated/inferred fact requires a value")
            _validate_value(self.value)
            if self.unit in {"workers", "units", "vehicles"}:
                if isinstance(self.value, bool) or not isinstance(self.value, int) or self.value < 0:
                    raise CompanyStateError(f"{self.unit} value must be a non-negative integer")
            if self.unit in {"km", "days", "hours"} and isinstance(self.value, (int, Decimal)) and not isinstance(self.value, bool) and self.value < 0:
                raise CompanyStateError(f"{self.unit} value cannot be negative")
        serialized = _canonical_json(_value_to_json(self.value)).encode("utf-8")
        if len(serialized) > MAX_SERIALIZED_VALUE_BYTES:
            raise CompanyStateError("fact value is too large")

    @property
    def semantic_key(self) -> tuple[str, str, str | None]:
        return (self.category.value, self.code, self.scope)

    @property
    def fact_id(self) -> str:
        material = {
            "category": self.category.value,
            "code": self.code,
            "scope": self.scope,
            "knowledge": self.knowledge.value,
            "value": _value_to_json(self.value),
            "unit": self.unit,
            "effective_from": _iso(self.effective_from),
            "effective_until": _iso(self.effective_until),
            "freshness_until": _iso(self.freshness_until),
            "provenance": self.provenance.to_dict(),
        }
        return "cf_" + hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()[:24]

    def freshness(self, as_of: datetime) -> FreshnessState:
        now = _utc(as_of, "as_of")
        if self.effective_from and now < self.effective_from:
            return FreshnessState.NOT_YET_EFFECTIVE
        if self.effective_until and now > self.effective_until:
            return FreshnessState.EXPIRED
        if self.freshness_until and now > self.freshness_until:
            return FreshnessState.STALE
        if self.effective_from or self.effective_until or self.freshness_until or self.provenance.verified_at:
            return FreshnessState.CURRENT
        return FreshnessState.UNKNOWN

    def to_dict(self, *, as_of: datetime | None = None) -> dict[str, Any]:
        payload = {
            "fact_id": self.fact_id,
            "category": self.category.value,
            "code": self.code,
            "scope": self.scope,
            "knowledge": self.knowledge.value,
            "value": _value_to_json(self.value),
            "unit": self.unit,
            "effective_from": _iso(self.effective_from),
            "effective_until": _iso(self.effective_until),
            "freshness_until": _iso(self.freshness_until),
            "provenance": self.provenance.to_dict(),
            "supersedes": list(self.supersedes),
        }
        if as_of is not None:
            payload["freshness"] = self.freshness(as_of).value
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompanyFact":
        if not isinstance(data, Mapping):
            raise CompanyStateError("fact must be an object")
        value = data.get("value")
        if isinstance(value, Mapping) and set(value.keys()) == {"amount", "currency"}:
            value = Money.from_dict(value)
        return cls(
            category=data.get("category"),
            code=data.get("code", ""),
            knowledge=data.get("knowledge"),
            value=value,
            provenance=Provenance.from_dict(data.get("provenance") or {}),
            scope=data.get("scope"),
            unit=data.get("unit"),
            effective_from=_parse_dt(data.get("effective_from"), "effective_from"),
            effective_until=_parse_dt(data.get("effective_until"), "effective_until"),
            freshness_until=_parse_dt(data.get("freshness_until"), "freshness_until"),
            supersedes=tuple(data.get("supersedes") or ()),
        )


@dataclass(frozen=True)
class CompanyState:
    account_id: str
    as_of: datetime
    facts: tuple[CompanyFact, ...] = ()
    company_ref: str | None = None
    state_version: int = 0
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        account_id = _account(self.account_id)
        object.__setattr__(self, "account_id", account_id)
        object.__setattr__(self, "as_of", _utc(self.as_of, "as_of"))
        object.__setattr__(self, "company_ref", _bounded_optional_text(self.company_ref, 128, "company_ref"))
        if self.contract_version != CONTRACT_VERSION:
            raise CompanyStateError(f"unsupported contract_version: {self.contract_version}")
        if isinstance(self.state_version, bool) or not isinstance(self.state_version, int) or self.state_version < 0:
            raise CompanyStateError("state_version must be a non-negative integer")
        if len(self.facts) > MAX_FACTS:
            raise CompanyStateError("too many company facts")
        if any(not isinstance(fact, CompanyFact) for fact in self.facts):
            raise CompanyStateError("facts must contain CompanyFact values")
        dedup: dict[str, CompanyFact] = {}
        for fact in self.facts:
            dedup.setdefault(fact.fact_id, fact)
        facts = tuple(sorted(dedup.values(), key=lambda f: (f.category.value, f.code, f.scope or "", f.fact_id)))
        object.__setattr__(self, "facts", facts)
        self._validate_supersession()
        self._validate_capacity_invariants()
        if len(_canonical_json(self._fingerprint_material()).encode("utf-8")) > MAX_SNAPSHOT_BYTES:
            raise CompanyStateError("company state snapshot is too large")

    def _validate_supersession(self) -> None:
        known = {fact.fact_id: fact for fact in self.facts}
        for fact in self.facts:
            if fact.fact_id in fact.supersedes:
                raise CompanyStateError("fact cannot supersede itself")
            for prior_id in fact.supersedes:
                prior = known.get(prior_id)
                if prior is None:
                    raise CompanyStateError("supersedes references unknown fact")
                if prior.semantic_key != fact.semantic_key:
                    raise CompanyStateError("supersedes must reference the same semantic fact")
        graph = {fact.fact_id: set(fact.supersedes) for fact in self.facts}
        for start in graph:
            stack = [start]
            seen: set[str] = set()
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                for target in graph.get(node, ()):
                    if target == start:
                        raise CompanyStateError("supersession cycle detected")
                    stack.append(target)

    def _validate_capacity_invariants(self) -> None:
        def factual_value(code: str, category: FactCategory) -> Any:
            candidates = [
                fact for fact in self.current_facts()
                if fact.code == code and fact.category is category and fact.knowledge is KnowledgeState.FACT
            ]
            values = {_canonical_json(_value_to_json(fact.value)): fact.value for fact in candidates}
            return next(iter(values.values())) if len(values) == 1 else None

        total = factual_value("crew.total_count", FactCategory.CAPACITY)
        available = factual_value("crew.available_count", FactCategory.AVAILABILITY)
        if isinstance(total, int) and isinstance(available, int) and available > total:
            raise CompanyStateError("known available crew cannot exceed known total crew")

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256(_canonical_json(self._fingerprint_material()).encode("utf-8")).hexdigest()
        return f"cs1_{digest}"

    def _fingerprint_material(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "fingerprint_version": FINGERPRINT_VERSION,
            "account_id": self.account_id,
            "company_ref": self.company_ref,
            "as_of": _iso(self.as_of),
            "facts": [fact.to_dict() for fact in self.facts],
        }

    def _superseded_ids(self, *, as_of: datetime) -> set[str]:
        """Return superseded ids whose replacing fact is already effective.

        A future-dated replacement must not erase the current fact before its
        effective window begins. Once the replacement becomes effective, its
        supersession remains authoritative even if that replacement later becomes
        stale or expires; historical truth must not be silently resurrected.
        """
        at = _utc(as_of, "as_of")
        return {
            item
            for fact in self.facts
            if fact.effective_from is None or at >= fact.effective_from
            for item in fact.supersedes
        }

    def active_facts(self, *, as_of: datetime | None = None) -> tuple[CompanyFact, ...]:
        at = _utc(as_of or self.as_of, "as_of")
        superseded = self._superseded_ids(as_of=at)
        return tuple(
            fact for fact in self.facts
            if fact.fact_id not in superseded
            and fact.freshness(at) not in {FreshnessState.EXPIRED, FreshnessState.NOT_YET_EFFECTIVE}
        )

    def current_facts(self, *, as_of: datetime | None = None) -> tuple[CompanyFact, ...]:
        """Return usable current facts; stale remains visible but is not current truth."""
        at = _utc(as_of or self.as_of, "as_of")
        return tuple(fact for fact in self.active_facts(as_of=at) if fact.freshness(at) is not FreshnessState.STALE)

    def conflicts(self, *, as_of: datetime | None = None) -> tuple[dict[str, Any], ...]:
        grouped: dict[tuple[str, str, str | None], list[CompanyFact]] = {}
        for fact in self.current_facts(as_of=as_of):
            if fact.knowledge is KnowledgeState.UNKNOWN:
                continue
            grouped.setdefault(fact.semantic_key, []).append(fact)
        result = []
        for key, facts in grouped.items():
            values = {_canonical_json(_value_to_json(fact.value)) for fact in facts}
            if len(values) > 1:
                result.append({
                    "category": key[0], "code": key[1], "scope": key[2],
                    "fact_ids": sorted(fact.fact_id for fact in facts),
                })
        return tuple(sorted(result, key=lambda item: (item["category"], item["code"], item.get("scope") or "")))

    def unknowns(self, *, as_of: datetime | None = None) -> tuple[str, ...]:
        at = _utc(as_of or self.as_of, "as_of")
        codes: set[str] = set()
        for fact in self.active_facts(as_of=at):
            if fact.knowledge is KnowledgeState.UNKNOWN or fact.freshness(at) is FreshnessState.STALE:
                codes.add(fact.code)
        return tuple(sorted(codes))

    def single_current_value(self, code: str, *, category: FactCategory | None = None, as_of: datetime | None = None) -> Any:
        candidates = [
            fact for fact in self.current_facts(as_of=as_of)
            if fact.code == code and (category is None or fact.category is category)
            and fact.knowledge is not KnowledgeState.UNKNOWN
        ]
        if not candidates:
            return None
        values = {_canonical_json(_value_to_json(fact.value)): fact.value for fact in candidates}
        return next(iter(values.values())) if len(values) == 1 else None

    def with_version(self, version: int) -> "CompanyState":
        return CompanyState(
            account_id=self.account_id,
            company_ref=self.company_ref,
            as_of=self.as_of,
            facts=self.facts,
            state_version=version,
            contract_version=self.contract_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "account_id": self.account_id,
            "company_ref": self.company_ref,
            "as_of": _iso(self.as_of),
            "state_version": self.state_version,
            "fingerprint": self.fingerprint,
            "facts": [fact.to_dict(as_of=self.as_of) for fact in self.facts],
            "unknowns": list(self.unknowns()),
            "conflicts": list(self.conflicts()),
            "quality": self.quality_summary(),
        }

    def quality_summary(self) -> dict[str, int]:
        counts = {
            "known": 0,
            "estimate": 0,
            "assumption": 0,
            "inference": 0,
            "unknown": 0,
            "stale": 0,
            "conflict": len(self.conflicts()),
        }
        for fact in self.active_facts():
            if fact.freshness(self.as_of) is FreshnessState.STALE:
                counts["stale"] += 1
            elif fact.knowledge is KnowledgeState.UNKNOWN:
                counts["unknown"] += 1
            elif fact.knowledge is KnowledgeState.FACT:
                counts["known"] += 1
            elif fact.knowledge is KnowledgeState.ESTIMATE:
                counts["estimate"] += 1
            elif fact.knowledge is KnowledgeState.ASSUMPTION:
                counts["assumption"] += 1
            elif fact.knowledge is KnowledgeState.INFERENCE:
                counts["inference"] += 1
        return counts

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, trusted_account_id: str | None = None) -> "CompanyState":
        if not isinstance(data, Mapping):
            raise CompanyStateError("company state must be an object")
        account = _account(trusted_account_id or data.get("account_id"))
        if trusted_account_id is not None and data.get("account_id") not in (None, account):
            raise TenantBoundaryError("payload account_id does not match trusted account")
        as_of = _parse_dt(data.get("as_of"), "as_of")
        if as_of is None:
            raise CompanyStateError("as_of is required")
        raw_version = data.get("state_version", 0)
        if isinstance(raw_version, bool) or not isinstance(raw_version, int) or raw_version < 0:
            raise CompanyStateError("state_version must be a non-negative integer")
        state = cls(
            account_id=account,
            company_ref=data.get("company_ref"),
            as_of=as_of,
            facts=tuple(CompanyFact.from_dict(item) for item in (data.get("facts") or ())),
            state_version=raw_version,
            contract_version=str(data.get("contract_version") or CONTRACT_VERSION),
        )
        supplied = data.get("fingerprint")
        if supplied not in (None, state.fingerprint):
            raise CompanyStateError("company state fingerprint does not match content")
        return state


def build_state(*, account_id: str, as_of: datetime, facts: Iterable[CompanyFact], company_ref: str | None = None) -> CompanyState:
    return CompanyState(account_id=account_id, company_ref=company_ref, as_of=as_of, facts=tuple(facts))


def validate_account_id(value: Any) -> str:
    """Validate a trusted tenant identifier without inventing a default tenant."""
    return _account(value)


def _enum(enum_cls, value, label):
    try:
        return value if isinstance(value, enum_cls) else enum_cls(str(value))
    except (ValueError, TypeError) as exc:
        raise CompanyStateError(f"invalid {label}") from exc


def _account(value: Any) -> str:
    account = str(value or "").strip()
    if not _ACCOUNT_RE.fullmatch(account):
        raise TenantBoundaryError("account_id is required and must be a valid trusted tenant identifier")
    return account


def _bounded_optional_text(value: Any, limit: int, label: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise CompanyStateError(f"{label} is invalid or too long")
    return text


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CompanyStateError(f"{label} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _utc_optional(value: datetime | None, label: str) -> datetime | None:
    return None if value is None else _utc(value, label)


def _parse_dt(value: Any, label: str) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _utc(value, label)
    if not isinstance(value, str) or len(value) > 64:
        raise CompanyStateError(f"{label} must be an ISO datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CompanyStateError(f"{label} must be an ISO datetime") from exc
    return _utc(parsed, label)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def _validate_value(value: Any, *, depth: int = 0) -> None:
    if depth > MAX_VALUE_DEPTH:
        raise CompanyStateError("fact value nesting is too deep")
    if value is None or isinstance(value, (str, bool, int, Decimal, Money)):
        if isinstance(value, str) and (len(value) > MAX_TEXT or any(ord(ch) < 32 for ch in value)):
            raise CompanyStateError("fact text is invalid or too long")
        if isinstance(value, Decimal) and not value.is_finite():
            raise CompanyStateError("decimal value must be finite")
        return
    if isinstance(value, float):
        raise CompanyStateError("binary float values are not accepted in company-state facts")
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_COLLECTION_ITEMS:
            raise CompanyStateError("fact collection is too large")
        for item in value:
            _validate_value(item, depth=depth + 1)
        return
    if isinstance(value, Mapping):
        if len(value) > MAX_MAPPING_ITEMS:
            raise CompanyStateError("fact mapping is too large")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise CompanyStateError("fact mapping keys must be non-empty strings")
            _bounded_optional_text(key, 96, "fact mapping key")
            _validate_value(item, depth=depth + 1)
        return
    raise CompanyStateError(f"unsupported fact value type: {type(value).__name__}")


def _value_to_json(value: Any) -> Any:
    if isinstance(value, Money):
        return value.to_dict()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, tuple):
        return [_value_to_json(item) for item in value]
    if isinstance(value, list):
        return [_value_to_json(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _value_to_json(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
