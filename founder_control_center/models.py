from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TruthState(str, Enum):
    GREEN = "GREEN"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


class ActionLevel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


@dataclass
class Evidence:
    source: str
    observed_at: str | None = None
    freshness_seconds: int | None = None
    kind: str = "unknown"
    detail: str | None = None
    url: str | None = None

    def freshness_state(self, now: datetime | None = None) -> TruthState:
        if not self.observed_at:
            return TruthState.UNKNOWN
        try:
            dt = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            return TruthState.UNKNOWN
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        now = now.astimezone(timezone.utc)
        if (dt - now).total_seconds() > 300:
            return TruthState.UNKNOWN
        age = max(0, int((now - dt).total_seconds()))
        if self.freshness_seconds is not None and age > self.freshness_seconds:
            return TruthState.STALE
        return TruthState.GREEN


@dataclass
class Metric:
    key: str
    label: str
    value: Any = None
    unit: str | None = None
    state: TruthState = TruthState.UNKNOWN
    evidence: Evidence | None = None


@dataclass
class Risk:
    title: str
    severity: str = "UNKNOWN"
    category: str = "strategic"
    detail: str | None = None
    evidence: Evidence | None = None


@dataclass
class FactoryState:
    name: str
    active: str = "UNKNOWN"
    next: str = "UNKNOWN"
    wait: str = "NONE"
    material_delta: str | None = None
    evidence: Evidence | None = None
    freshness: TruthState = TruthState.UNKNOWN


@dataclass
class RepositoryState:
    full_name: str | None = None
    branch: str | None = None
    commit: str | None = None
    ci: TruthState = TruthState.UNKNOWN
    evidence: Evidence | None = None


@dataclass
class ApplicationState:
    name: str | None = None
    url: str | None = None
    deployment: TruthState = TruthState.UNKNOWN
    health: TruthState = TruthState.UNKNOWN
    evidence: Evidence | None = None
    deployment_evidence: Evidence | None = None
    health_evidence: Evidence | None = None


@dataclass
class CompanyManifest:
    id: str
    name: str
    mission: str
    kind: str = "company"
    status: str = "UNKNOWN"
    stage: str = "UNKNOWN"
    active: str = "UNKNOWN"
    next: str = "UNKNOWN"
    wait: str = "NONE"
    business_model: str = "UNKNOWN"
    icp: str = "UNKNOWN"
    pricing: str = "UNKNOWN"
    revenue: Metric = field(default_factory=lambda: Metric("revenue", "Revenue"))
    pipeline: Metric = field(default_factory=lambda: Metric("pipeline", "Pipeline"))
    customers: Metric = field(default_factory=lambda: Metric("customers", "Customers"))
    metrics: list[Metric] = field(default_factory=list)
    risks: list[Risk] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    factories: list[FactoryState] = field(default_factory=list)
    repository: RepositoryState = field(default_factory=RepositoryState)
    application: ApplicationState = field(default_factory=ApplicationState)
    priorities: list[str] = field(default_factory=list)
    last_update: str | None = None
    data_freshness: TruthState = TruthState.UNKNOWN
    synthetic: bool = False
    source_note: str = "No connected source"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        return _normalize_enums(result)


def _normalize_enums(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_normalize_enums(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_enums(v) for k, v in value.items()}
    return value
