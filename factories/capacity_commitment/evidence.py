from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Context, Decimal, InvalidOperation, localcontext
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_NORMALIZATION_CONTEXT = Context(prec=60, Emin=-999999, Emax=999999)


class EvidenceKind(str, Enum):
    CONTRACT = "CONTRACT"
    AMENDMENT = "AMENDMENT"
    NOMINATION = "NOMINATION"
    FORECAST = "FORECAST"
    RELEASE = "RELEASE"
    ACTUALS = "ACTUALS"
    COST_BASIS = "COST_BASIS"
    MITIGATION = "MITIGATION"
    PRIOR_PAYMENT = "PRIOR_PAYMENT"
    NOTICE = "NOTICE"
    CORRESPONDENCE = "CORRESPONDENCE"
    OTHER = "OTHER"


class ReviewState(str, Enum):
    UNREVIEWED = "UNREVIEWED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class FactType(str, Enum):
    CUSTOMER_ID = "CUSTOMER_ID"
    PROGRAM_ID = "PROGRAM_ID"
    CONTRACT_ID = "CONTRACT_ID"
    NOMINATION_ID = "NOMINATION_ID"
    CURRENCY = "CURRENCY"
    UNIT = "UNIT"
    COMMITMENT_STATE = "COMMITMENT_STATE"
    COMMITTED_UNITS = "COMMITTED_UNITS"
    ACTUAL_UNITS = "ACTUAL_UNITS"
    DEDICATED_COST = "DEDICATED_COST"
    AMORTIZATION_BASIS_UNITS = "AMORTIZATION_BASIS_UNITS"
    MITIGATION = "MITIGATION"
    PRIOR_PAYMENT = "PRIOR_PAYMENT"
    EXPLICIT_RECOVERY_RIGHT = "EXPLICIT_RECOVERY_RIGHT"
    NOTICE_VALID = "NOTICE_VALID"
    DEADLINE = "DEADLINE"


_NUMERIC_FACTS = {
    FactType.COMMITTED_UNITS,
    FactType.ACTUAL_UNITS,
    FactType.DEDICATED_COST,
    FactType.AMORTIZATION_BASIS_UNITS,
    FactType.MITIGATION,
    FactType.PRIOR_PAYMENT,
}
_BOOLEAN_FACTS = {FactType.EXPLICIT_RECOVERY_RIGHT, FactType.NOTICE_VALID}
_SINGLETON_FACTS = set(FactType) - {FactType.ACTUAL_UNITS}


@dataclass(frozen=True)
class EvidenceSource:
    tenant_id: str
    evidence_id: str
    kind: EvidenceKind
    display_name: str
    external_ref: str
    sha256: str
    captured_at: str


@dataclass(frozen=True)
class ExtractedFact:
    tenant_id: str
    fact_id: str
    evidence_id: str
    fact_type: FactType
    raw_value: str
    normalized_value: str
    scope_ref: str | None = None
    page_ref: str | None = None
    clause_ref: str | None = None
    review_state: ReviewState = ReviewState.UNREVIEWED


@dataclass(frozen=True)
class NormalizedEvidence:
    singleton_values: Mapping[str, str]
    actual_units: Decimal | None
    actual_scopes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    conflicts: tuple[str, ...]

    @property
    def conflict_free(self) -> bool:
        return not self.conflicts


def sha256_bytes(content: bytes) -> str:
    if not isinstance(content, bytes):
        raise ValueError("content must be bytes")
    return hashlib.sha256(content).hexdigest()


def _required_text(value, field: str, *, max_len: int = 500) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    value = value.strip()
    if len(value) > max_len:
        raise ValueError(f"{field} is too long")
    if "\x00" in value:
        raise ValueError(f"{field} contains NUL")
    return value


def _safe_id(value, field: str) -> str:
    value = _required_text(value, field, max_len=200)
    if not _SAFE_ID_RE.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def _optional_ref(value, field: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field, max_len=200)


def _normalize_fact_value(fact_type: FactType, value: str) -> str:
    value = _required_text(value, "normalized_value", max_len=500)
    if fact_type in _NUMERIC_FACTS:
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{fact_type.value} must be an exact decimal string") from exc
        if not parsed.is_finite() or parsed < 0:
            raise ValueError(f"{fact_type.value} must be finite and non-negative")
        return format(parsed, "f")
    if fact_type in _BOOLEAN_FACTS:
        if value not in {"true", "false", "unknown"}:
            raise ValueError(f"{fact_type.value} must be true, false, or unknown")
        return value
    if fact_type is FactType.CURRENCY:
        value = value.upper()
        if len(value) != 3 or not value.isascii() or not value.isalpha():
            raise ValueError("CURRENCY must be a 3-letter ASCII code")
        return value
    if fact_type is FactType.COMMITMENT_STATE:
        if value not in {"FIRM", "FLEX_WINDOW", "FORECAST_ONLY", "AMBIGUOUS", "NONE"}:
            raise ValueError("COMMITMENT_STATE is invalid")
        return value
    return value


def validate_source(source: EvidenceSource) -> EvidenceSource:
    tenant_id = _required_text(source.tenant_id, "tenant_id", max_len=200)
    evidence_id = _safe_id(source.evidence_id, "evidence_id")
    if not isinstance(source.kind, EvidenceKind):
        raise ValueError("kind must be an EvidenceKind")
    display_name = _required_text(source.display_name, "display_name", max_len=300)
    external_ref = _required_text(source.external_ref, "external_ref", max_len=500)
    if "?" in external_ref or "#" in external_ref:
        raise ValueError("external_ref must not contain query or fragment secrets")
    if not isinstance(source.sha256, str) or not _SHA256_RE.fullmatch(source.sha256):
        raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
    captured_at = _required_text(source.captured_at, "captured_at", max_len=80)
    return EvidenceSource(
        tenant_id=tenant_id,
        evidence_id=evidence_id,
        kind=source.kind,
        display_name=display_name,
        external_ref=external_ref,
        sha256=source.sha256,
        captured_at=captured_at,
    )


def validate_fact(fact: ExtractedFact) -> ExtractedFact:
    tenant_id = _required_text(fact.tenant_id, "tenant_id", max_len=200)
    fact_id = _safe_id(fact.fact_id, "fact_id")
    evidence_id = _safe_id(fact.evidence_id, "evidence_id")
    if not isinstance(fact.fact_type, FactType):
        raise ValueError("fact_type must be a FactType")
    if not isinstance(fact.review_state, ReviewState):
        raise ValueError("review_state must be a ReviewState")
    raw_value = _required_text(fact.raw_value, "raw_value", max_len=2000)
    normalized_value = _normalize_fact_value(fact.fact_type, fact.normalized_value)
    scope_ref = _optional_ref(fact.scope_ref, "scope_ref")
    page_ref = _optional_ref(fact.page_ref, "page_ref")
    clause_ref = _optional_ref(fact.clause_ref, "clause_ref")
    if fact.fact_type is FactType.ACTUAL_UNITS and not scope_ref:
        raise ValueError("ACTUAL_UNITS requires scope_ref for deduplication")
    return ExtractedFact(
        tenant_id=tenant_id,
        fact_id=fact_id,
        evidence_id=evidence_id,
        fact_type=fact.fact_type,
        raw_value=raw_value,
        normalized_value=normalized_value,
        scope_ref=scope_ref,
        page_ref=page_ref,
        clause_ref=clause_ref,
        review_state=fact.review_state,
    )


class EvidenceRepository:
    """Immutable, tenant-scoped provenance/fact registry.

    Raw contract bytes are intentionally not stored here. The registry records
    authorized external references, hashes, locations and reviewed structured
    facts. Positive case inputs must be derived only from CONFIRMED facts.
    """

    def __init__(self, db_path: str):
        if not db_path or db_path == ":memory:":
            raise ValueError("db_path must be a durable filesystem path")
        self.db_path = str(Path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capacity_commitment_evidence_sources (
                    tenant_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    external_ref TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, evidence_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capacity_commitment_evidence_facts (
                    tenant_id TEXT NOT NULL,
                    fact_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    fact_type TEXT NOT NULL,
                    raw_value TEXT NOT NULL,
                    normalized_value TEXT NOT NULL,
                    scope_ref TEXT,
                    page_ref TEXT,
                    clause_ref TEXT,
                    review_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    PRIMARY KEY (tenant_id, fact_id)
                )
                """
            )

    def save_source(self, source: EvidenceSource) -> bool:
        source = validate_source(source)
        now = datetime.now(timezone.utc).isoformat()
        values = (
            source.tenant_id,
            source.evidence_id,
            source.kind.value,
            source.display_name,
            source.external_ref,
            source.sha256,
            source.captured_at,
            now,
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO capacity_commitment_evidence_sources
                    (tenant_id, evidence_id, kind, display_name, external_ref, sha256, captured_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            return True
        except sqlite3.IntegrityError as exc:
            existing = self.load_source(tenant_id=source.tenant_id, evidence_id=source.evidence_id)
            if existing == source:
                return False
            raise FileExistsError("evidence source already exists with different provenance") from exc

    def load_source(self, *, tenant_id: str, evidence_id: str) -> EvidenceSource:
        tenant_id = _required_text(tenant_id, "tenant_id", max_len=200)
        evidence_id = _safe_id(evidence_id, "evidence_id")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, evidence_id, kind, display_name, external_ref, sha256, captured_at
                FROM capacity_commitment_evidence_sources
                WHERE tenant_id=? AND evidence_id=?
                """,
                (tenant_id, evidence_id),
            ).fetchone()
        if row is None:
            raise KeyError("evidence source not found")
        return validate_source(
            EvidenceSource(
                tenant_id=row["tenant_id"],
                evidence_id=row["evidence_id"],
                kind=EvidenceKind(row["kind"]),
                display_name=row["display_name"],
                external_ref=row["external_ref"],
                sha256=row["sha256"],
                captured_at=row["captured_at"],
            )
        )

    def list_sources(self, *, tenant_id: str) -> list[EvidenceSource]:
        tenant_id = _required_text(tenant_id, "tenant_id", max_len=200)
        with self._connect() as conn:
            ids = [
                row["evidence_id"]
                for row in conn.execute(
                    "SELECT evidence_id FROM capacity_commitment_evidence_sources WHERE tenant_id=? ORDER BY evidence_id",
                    (tenant_id,),
                ).fetchall()
            ]
        return [self.load_source(tenant_id=tenant_id, evidence_id=item) for item in ids]

    def save_fact(self, fact: ExtractedFact) -> bool:
        fact = validate_fact(fact)
        self.load_source(tenant_id=fact.tenant_id, evidence_id=fact.evidence_id)
        if fact.review_state is not ReviewState.UNREVIEWED:
            raise ValueError("new extracted facts must start UNREVIEWED")
        now = datetime.now(timezone.utc).isoformat()
        values = (
            fact.tenant_id,
            fact.fact_id,
            fact.evidence_id,
            fact.fact_type.value,
            fact.raw_value,
            fact.normalized_value,
            fact.scope_ref,
            fact.page_ref,
            fact.clause_ref,
            fact.review_state.value,
            now,
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO capacity_commitment_evidence_facts
                    (tenant_id, fact_id, evidence_id, fact_type, raw_value, normalized_value,
                     scope_ref, page_ref, clause_ref, review_state, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            return True
        except sqlite3.IntegrityError as exc:
            existing = self.load_fact(tenant_id=fact.tenant_id, fact_id=fact.fact_id)
            if existing == fact:
                return False
            raise FileExistsError("evidence fact already exists with different content") from exc

    def load_fact(self, *, tenant_id: str, fact_id: str) -> ExtractedFact:
        tenant_id = _required_text(tenant_id, "tenant_id", max_len=200)
        fact_id = _safe_id(fact_id, "fact_id")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT tenant_id, fact_id, evidence_id, fact_type, raw_value, normalized_value,
                       scope_ref, page_ref, clause_ref, review_state
                FROM capacity_commitment_evidence_facts
                WHERE tenant_id=? AND fact_id=?
                """,
                (tenant_id, fact_id),
            ).fetchone()
        if row is None:
            raise KeyError("evidence fact not found")
        return validate_fact(
            ExtractedFact(
                tenant_id=row["tenant_id"],
                fact_id=row["fact_id"],
                evidence_id=row["evidence_id"],
                fact_type=FactType(row["fact_type"]),
                raw_value=row["raw_value"],
                normalized_value=row["normalized_value"],
                scope_ref=row["scope_ref"],
                page_ref=row["page_ref"],
                clause_ref=row["clause_ref"],
                review_state=ReviewState(row["review_state"]),
            )
        )

    def review_fact(self, *, tenant_id: str, fact_id: str, decision: ReviewState) -> bool:
        if decision not in {ReviewState.CONFIRMED, ReviewState.REJECTED}:
            raise ValueError("review decision must be CONFIRMED or REJECTED")
        current = self.load_fact(tenant_id=tenant_id, fact_id=fact_id)
        if current.review_state is decision:
            return False
        if current.review_state is not ReviewState.UNREVIEWED:
            raise FileExistsError("reviewed evidence fact is immutable")
        reviewed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE capacity_commitment_evidence_facts
                SET review_state=?, reviewed_at=?
                WHERE tenant_id=? AND fact_id=? AND review_state=?
                """,
                (decision.value, reviewed_at, tenant_id, fact_id, ReviewState.UNREVIEWED.value),
            ).rowcount
        if updated != 1:
            raise FileExistsError("evidence fact review state changed concurrently")
        return True

    def list_facts(self, *, tenant_id: str, review_state: ReviewState | None = None) -> list[ExtractedFact]:
        tenant_id = _required_text(tenant_id, "tenant_id", max_len=200)
        query = "SELECT fact_id FROM capacity_commitment_evidence_facts WHERE tenant_id=?"
        params: list[str] = [tenant_id]
        if review_state is not None:
            if not isinstance(review_state, ReviewState):
                raise ValueError("review_state must be a ReviewState")
            query += " AND review_state=?"
            params.append(review_state.value)
        query += " ORDER BY fact_id"
        with self._connect() as conn:
            ids = [row["fact_id"] for row in conn.execute(query, params).fetchall()]
        return [self.load_fact(tenant_id=tenant_id, fact_id=fact_id) for fact_id in ids]


def normalize_confirmed_facts(facts: Iterable[ExtractedFact]) -> NormalizedEvidence:
    confirmed = [validate_fact(fact) for fact in facts if fact.review_state is ReviewState.CONFIRMED]
    singleton_values: dict[str, str] = {}
    singleton_sources: dict[str, set[str]] = {}
    actual_by_scope: dict[str, tuple[Decimal, str]] = {}
    conflicts: list[str] = []
    evidence_refs: set[str] = set()

    for fact in confirmed:
        evidence_refs.add(fact.evidence_id)
        if fact.fact_type in _SINGLETON_FACTS:
            key = fact.fact_type.value
            previous = singleton_values.get(key)
            if previous is None:
                singleton_values[key] = fact.normalized_value
                singleton_sources[key] = {fact.evidence_id}
            elif previous != fact.normalized_value:
                conflicts.append(f"conflicting confirmed {key}")
                singleton_sources.setdefault(key, set()).add(fact.evidence_id)
            else:
                singleton_sources.setdefault(key, set()).add(fact.evidence_id)
            continue

        if fact.fact_type is FactType.ACTUAL_UNITS:
            assert fact.scope_ref is not None
            value = Decimal(fact.normalized_value)
            if fact.scope_ref in actual_by_scope:
                conflicts.append(f"duplicate confirmed ACTUAL_UNITS scope {fact.scope_ref}")
            else:
                actual_by_scope[fact.scope_ref] = (value, fact.evidence_id)

    actual_units = None
    if actual_by_scope and not any(item.startswith("duplicate confirmed ACTUAL_UNITS") for item in conflicts):
        with localcontext(_NORMALIZATION_CONTEXT):
            actual_units = sum((value for value, _source in actual_by_scope.values()), Decimal("0"))

    return NormalizedEvidence(
        singleton_values=dict(sorted(singleton_values.items())),
        actual_units=actual_units,
        actual_scopes=tuple(sorted(actual_by_scope)),
        evidence_refs=tuple(sorted(evidence_refs)),
        conflicts=tuple(sorted(set(conflicts))),
    )
