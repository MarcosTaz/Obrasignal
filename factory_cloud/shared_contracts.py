from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class SharedContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class IdentityPrincipal:
    tenant_id: str
    subject: str
    roles: tuple[str, ...]
    issuer: str
    audience: str

    @classmethod
    def create(cls, *, tenant_id: str, subject: str, roles: Iterable[str], issuer: str, audience: str) -> "IdentityPrincipal":
        role_tuple = tuple(str(role).strip() for role in roles if str(role).strip())
        if not tenant_id.strip() or not subject.strip() or not issuer.strip() or not audience.strip():
            raise SharedContractError("identity principal requires tenant, subject, issuer and audience")
        if len(set(role_tuple)) != len(role_tuple):
            raise SharedContractError("identity roles must be unique")
        return cls(tenant_id.strip(), subject.strip(), role_tuple, issuer.strip(), audience.strip())

    def require(self, role: str) -> None:
        if role not in self.roles:
            raise SharedContractError("required tenant-scoped role missing")


@dataclass(frozen=True)
class EntitlementSnapshot:
    tenant_id: str
    plan_id: str
    status: str
    features: tuple[str, ...]
    provider_ref: str | None = None

    @classmethod
    def create(cls, *, tenant_id: str, plan_id: str, status: str, features: Iterable[str], provider_ref: str | None = None) -> "EntitlementSnapshot":
        normalized = tuple(sorted({str(feature).strip() for feature in features if str(feature).strip()}))
        if not tenant_id.strip() or not plan_id.strip():
            raise SharedContractError("entitlement requires tenant and plan")
        if status not in {"ACTIVE", "TRIAL", "PAST_DUE", "SUSPENDED", "CANCELLED"}:
            raise SharedContractError("invalid entitlement status")
        return cls(tenant_id.strip(), plan_id.strip(), status, normalized, provider_ref)

    def allows(self, feature: str) -> bool:
        return self.status in {"ACTIVE", "TRIAL"} and feature in self.features

    def require(self, feature: str) -> None:
        if not self.allows(feature):
            raise SharedContractError("feature entitlement denied")


@dataclass(frozen=True)
class ReleaseEvidence:
    revision: str
    required_checks: tuple[str, ...]
    successful_checks: tuple[str, ...]

    @classmethod
    def create(cls, *, revision: str, required_checks: Iterable[str], successful_checks: Iterable[str]) -> "ReleaseEvidence":
        if not _SHA_RE.fullmatch(revision):
            raise SharedContractError("release evidence requires exact SHA")
        required = tuple(sorted({str(item).strip() for item in required_checks if str(item).strip()}))
        successful = tuple(sorted({str(item).strip() for item in successful_checks if str(item).strip()}))
        if not required:
            raise SharedContractError("at least one required check is required")
        return cls(revision, required, successful)

    @property
    def ready(self) -> bool:
        return set(self.required_checks).issubset(self.successful_checks)

    def require_ready(self) -> None:
        if not self.ready:
            missing = sorted(set(self.required_checks) - set(self.successful_checks))
            raise SharedContractError("release checks incomplete: " + ", ".join(missing))
