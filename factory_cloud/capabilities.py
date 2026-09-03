from __future__ import annotations

from enum import StrEnum
from typing import Iterable


class Capability(StrEnum):
    READ_REPOSITORY = "READ_REPOSITORY"
    CREATE_BRANCH = "CREATE_BRANCH"
    WRITE_FILES = "WRITE_FILES"
    RUN_TESTS = "RUN_TESTS"
    CREATE_PR = "CREATE_PR"
    READ_CI = "READ_CI"
    UPDATE_BATON = "UPDATE_BATON"

    MERGE_MAIN = "MERGE_MAIN"
    DEPLOY_PRODUCTION = "DEPLOY_PRODUCTION"
    ACCESS_CUSTOMER_DATA = "ACCESS_CUSTOMER_DATA"
    ACTIVATE_BILLING = "ACTIVATE_BILLING"
    ROTATE_SECRETS = "ROTATE_SECRETS"
    CONTACT_CUSTOMERS = "CONTACT_CUSTOMERS"


SAFE_REPOSITORY_CAPABILITIES = frozenset(
    {
        Capability.READ_REPOSITORY,
        Capability.CREATE_BRANCH,
        Capability.WRITE_FILES,
        Capability.RUN_TESTS,
        Capability.CREATE_PR,
        Capability.READ_CI,
        Capability.UPDATE_BATON,
    }
)

HIGH_RISK_CAPABILITIES = frozenset(set(Capability) - set(SAFE_REPOSITORY_CAPABILITIES))


class CapabilityContractError(ValueError):
    pass


def parse_capabilities(
    values: Iterable[str | Capability] | None,
    *,
    allow_high_risk: bool = False,
    require_explicit: bool = True,
) -> frozenset[Capability]:
    if values is None:
        if require_explicit:
            raise CapabilityContractError("adapter capabilities must be explicitly declared")
        return frozenset()

    parsed: set[Capability] = set()
    for raw in values:
        try:
            capability = raw if isinstance(raw, Capability) else Capability(str(raw))
        except ValueError as exc:
            raise CapabilityContractError(f"unknown capability: {raw}") from exc
        parsed.add(capability)

    forbidden = parsed & HIGH_RISK_CAPABILITIES
    if forbidden and not allow_high_risk:
        names = ", ".join(sorted(item.value for item in forbidden))
        raise CapabilityContractError(f"high-risk capabilities require separate authority: {names}")
    return frozenset(parsed)


def require_capabilities(
    declared: Iterable[str | Capability],
    required: Iterable[str | Capability],
) -> frozenset[Capability]:
    declared_set = parse_capabilities(declared, require_explicit=False)
    required_set = parse_capabilities(required, require_explicit=False)
    missing = required_set - declared_set
    if missing:
        names = ", ".join(sorted(item.value for item in missing))
        raise CapabilityContractError(f"adapter lacks required capabilities: {names}")
    return required_set
