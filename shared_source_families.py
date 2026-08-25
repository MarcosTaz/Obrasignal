"""Canonical shared procurement-source families.

This module is intentionally a *fitness layer*, not a fourth connector framework.
It declares which production sources share a transport/standard contract and
validates that source-registry metadata cannot silently drift away from the code
family that actually implements ingestion.

Different OCDS transports stay separate because page-number APIs, opaque-cursor
APIs and monthly bulk+record hydration have materially different completeness
and failure semantics. eForms likewise groups the semantic standard while
allowing publisher-specific transport/parsing adapters.
"""
from dataclasses import dataclass
from types import MappingProxyType

from source_registry import SOURCES


@dataclass(frozen=True)
class SharedSourceFamily:
    family_id: str
    standard: str
    transport: str
    members: tuple[str, ...]
    invariant: str
    generic_module: str | None = None


FAMILIES = MappingProxyType({
    "TED_SEARCH": SharedSourceFamily(
        family_id="TED_SEARCH",
        standard="TED/eForms",
        transport="TED Search API",
        members=("TED",),
        invariant="central EU TED search contract; member countries must not grow bespoke TED search adapters",
        generic_module="ted_client",
    ),
    "EFORMS_XML": SharedSourceFamily(
        family_id="EFORMS_XML",
        standard="eForms",
        transport="publisher eForms XML export",
        members=("SERVICE_BUND_DE", "EE_RHR"),
        invariant="publisher transport may differ, but works taxonomy, lot identity and lifecycle must remain publisher-native",
    ),
    "OCDS_PAGE_API": SharedSourceFamily(
        family_id="OCDS_PAGE_API",
        standard="OCDS",
        transport="bounded date window + page number",
        members=("PY_DNCP", "ZA_ETENDERS", "DO_DGCP"),
        invariant="cursor advances only after every page in a bounded temporal window completes",
        generic_module="ocds_adapter",
    ),
    "OCDS_OPAQUE_CURSOR": SharedSourceFamily(
        family_id="OCDS_OPAQUE_CURSOR",
        standard="OCDS",
        transport="bounded date/time window + publisher opaque cursor",
        members=("UK_PROCUREMENT",),
        invariant="next links cannot escape the configured endpoint and repeated cursors fail closed",
        generic_module="ocds_cursor_adapter",
    ),
    "OCDS_MONTHLY_BULK": SharedSourceFamily(
        family_id="OCDS_MONTHLY_BULK",
        standard="OCDS",
        transport="monthly bulk discovery + bounded record hydration",
        members=("EC_SERCOP",),
        invariant="bulk discovers changed OCIDs; current compiled record state decides emitted observations",
        generic_module="ocds_bulk_adapter",
    ),
})


# Registry adapter claims that are deliberately shared. Source-specific wrappers
# are allowed, but a source claiming one of these adapter names must belong to
# the corresponding family.
_GENERIC_ADAPTER_FAMILY = MappingProxyType({
    "OCDSAPIConnector": "OCDS_PAGE_API",
    "OCDSMonthlyBulkConnector": "OCDS_MONTHLY_BULK",
    "TEDSearchAdapter": "TED_SEARCH",
})


def _families(value=None):
    return FAMILIES if value is None else value


def family_for_source(source, *, families=None):
    source = str(source or "").upper()
    matches = [family for family in _families(families).values() if source in family.members]
    if len(matches) > 1:
        raise RuntimeError(f"source {source} belongs to multiple shared families")
    return matches[0] if matches else None


def members_for_standard(standard, *, families=None):
    wanted = str(standard or "").strip().lower()
    return tuple(
        source
        for family in _families(families).values()
        if family.standard.lower() == wanted
        for source in family.members
    )


def audit_shared_families(registry=None, *, families=None):
    """Return deterministic fitness violations; empty tuple means healthy.

    The audit deliberately checks metadata/contracts only. It does not perform
    network I/O and therefore belongs in normal CI. ``families`` exists for
    isolated fitness testing; production callers use the immutable canonical map.
    """
    registry = registry or SOURCES
    family_map = _families(families)
    violations = []
    seen = {}

    for family in family_map.values():
        if not family.members:
            violations.append(f"{family.family_id}:empty_family")
        for source in family.members:
            previous = seen.get(source)
            if previous:
                violations.append(f"{source}:multiple_families:{previous},{family.family_id}")
            seen[source] = family.family_id
            meta = registry.get(source)
            if not meta:
                violations.append(f"{source}:missing_source_registry_entry")
                continue
            if not meta.get("official"):
                violations.append(f"{source}:not_official")
            if not meta.get("adapter"):
                violations.append(f"{source}:missing_adapter")
            if "incremental_sync" not in set(meta.get("capabilities") or ()) and source != "TED":
                violations.append(f"{source}:missing_incremental_sync_capability")

    for source, meta in registry.items():
        adapter = str(meta.get("adapter") or "")
        expected_family = _GENERIC_ADAPTER_FAMILY.get(adapter)
        if not expected_family:
            continue
        actual = seen.get(source)
        if actual != expected_family:
            violations.append(f"{source}:adapter_family_mismatch:{adapter}:{actual or 'none'}")

    return tuple(sorted(set(violations)))


def assert_shared_family_health(registry=None, *, families=None):
    violations = audit_shared_families(registry, families=families)
    if violations:
        raise RuntimeError("shared source family fitness failed: " + "; ".join(violations))
    return True
