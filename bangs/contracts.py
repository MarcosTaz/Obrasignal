from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol


class BangStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    GATED = "GATED"
    INVALID = "INVALID"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    FAILED = "FAILED"


class SideEffectClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    TENANT_WRITE = "TENANT_WRITE"
    EXTERNAL_SIDE_EFFECT = "EXTERNAL_SIDE_EFFECT"
    PRIVILEGED = "PRIVILEGED"


@dataclass(frozen=True)
class BangInvocation:
    command: str
    args: tuple[str, ...] = ()
    raw: str = ""


@dataclass(frozen=True)
class BangPrincipal:
    account_id: str
    permissions: frozenset[str] = frozenset()
    subject: str | None = None
    authenticated: bool = False


@dataclass(frozen=True)
class BangExecutionContext:
    principal: BangPrincipal
    idempotency_key: str | None = None


@dataclass(frozen=True)
class ProviderResult:
    status: BangStatus
    message: str
    data: Any = None
    warnings: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class BangResult:
    command: str
    status: BangStatus
    message: str
    data: Any
    warnings: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    capability: str | None
    execution_id: str
    generated_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "warnings": list(self.warnings),
            "evidence_refs": list(self.evidence_refs),
            "capability": self.capability,
            "execution_id": self.execution_id,
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class ProviderAvailability:
    present: bool
    enabled: bool = True
    gated: bool = False
    reason: str = ""


class BangProvider(Protocol):
    name: str

    def availability(self) -> ProviderAvailability: ...

    def execute(self, invocation: BangInvocation, context: BangExecutionContext) -> ProviderResult: ...


class BangObserver(Protocol):
    def record(self, event: Mapping[str, Any]) -> None: ...


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
