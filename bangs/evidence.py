from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import ipaddress
import re
from urllib.parse import urlsplit

class EvidenceBasis(str, Enum):
    LIVE_LIST_PRICE = "LIVE_LIST_PRICE"
    OFFICIAL_CATALOGUE = "OFFICIAL_CATALOGUE"
    SUPPLIER_QUOTE = "SUPPLIER_QUOTE"
    MARKET_OBSERVATION = "MARKET_OBSERVATION"
    HISTORICAL_PRICE = "HISTORICAL_PRICE"
    USER_INPUT = "USER_INPUT"
    ESTIMATE = "ESTIMATE"
    UNKNOWN = "UNKNOWN"
    PROVIDER_FACT = "PROVIDER_FACT"

class TaxBasis(str, Enum):
    VAT_INCLUDED = "VAT_INCLUDED"
    VAT_EXCLUDED = "VAT_EXCLUDED"
    TAX_UNKNOWN = "TAX_UNKNOWN"

class Visibility(str, Enum):
    PUBLIC = "PUBLIC"
    TENANT_PRIVATE = "TENANT_PRIVATE"

class Availability(str, Enum):
    AVAILABLE = "AVAILABLE"
    LIMITED = "LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"

class ConfirmationState(str, Enum):
    PRICE_OBSERVED = "PRICE_OBSERVED"
    AVAILABILITY_CONFIRMED = "AVAILABILITY_CONFIRMED"
    AVAILABILITY_UNKNOWN = "AVAILABILITY_UNKNOWN"

class RequirementBasis(str, Enum):
    DOCUMENT_EXPLICIT = "DOCUMENT_EXPLICIT"
    BOQ_EXPLICIT = "BOQ_EXPLICIT"
    USER_SUPPLIED = "USER_SUPPLIED"
    SYSTEM_DERIVED = "SYSTEM_DERIVED"
    ESTIMATE = "ESTIMATE"
    UNKNOWN = "UNKNOWN"

class FreshnessState(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def validate_evidence_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if len(value) > 2048 or _CONTROL_RE.search(value):
        raise ValueError("unsafe evidence URL")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("evidence URL must be a public http(s) reference")
    return value


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    source_name: str
    basis: EvidenceBasis
    observed_at: datetime
    source_ref: str | None = None
    source_url: str | None = None
    valid_until: datetime | None = None
    location: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        name = str(self.source_name or "").strip()
        if not name or len(name) > 160 or _CONTROL_RE.search(name):
            raise ValueError("invalid source name")
        observed = _utc(self.observed_at)
        valid = _utc(self.valid_until) if self.valid_until else None
        # A system may observe/import a quote after its contractual validity has
        # already expired. Preserve that fact so freshness policy can fail closed
        # instead of rejecting useful historical evidence.
        object.__setattr__(self, "source_name", name)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "valid_until", valid)
        object.__setattr__(self, "source_url", validate_evidence_url(self.source_url))
        if self.source_ref is not None and len(str(self.source_ref)) > 512:
            raise ValueError("source reference too long")


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    max_age: timedelta

    def __post_init__(self) -> None:
        if self.max_age.total_seconds() <= 0:
            raise ValueError("max_age must be positive")

    def state(self, evidence: SourceEvidence, *, now: datetime) -> FreshnessState:
        now_utc = _utc(now)
        if evidence.valid_until and now_utc > evidence.valid_until:
            return FreshnessState.EXPIRED
        return FreshnessState.STALE if now_utc - evidence.observed_at > self.max_age else FreshnessState.CURRENT


@dataclass(frozen=True, slots=True)
class ProviderEndpointPolicy:
    allowed_hosts: frozenset[str]

    def __post_init__(self) -> None:
        normalized = frozenset(str(h).strip().lower().rstrip(".") for h in self.allowed_hosts if str(h).strip())
        if not normalized:
            raise ValueError("provider endpoint allow-list cannot be empty")
        object.__setattr__(self, "allowed_hosts", normalized)

    def validate(self, url: str) -> str:
        url = validate_evidence_url(url) or ""
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified):
            raise ValueError("private or local provider endpoint rejected")
        if host not in self.allowed_hosts:
            raise ValueError("provider endpoint host is not allow-listed")
        return url
