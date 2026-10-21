"""Declarative capability registry for ObraSignal's modular-monolith architecture.

This is intentionally small: it records lifecycle, health, ownership, contracts,
events, dependencies and rollout controls without creating a service framework.
Product/runtime wiring remains explicit elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CapabilityState = Literal["RESEARCH", "EXPERIMENT", "PILOT", "ENABLED", "DISABLED", "DEPRECATED"]
HealthState = Literal["HEALTHY", "DEGRADED", "UNAVAILABLE"]


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    state: CapabilityState
    health: HealthState
    owner_domain: str
    contract_versions: tuple[str, ...] = ()
    publishes_events: tuple[str, ...] = ()
    consumes_events: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    feature_flag: str | None = None
    kill_switch_required: bool = False
    private_data_owner: str = ""
    failure_mode: str = "degrade_without_platform_failure"


def _c(
    name: str,
    state: CapabilityState,
    owner_domain: str,
    *,
    health: HealthState = "HEALTHY",
    contract_versions: tuple[str, ...] = (),
    publishes_events: tuple[str, ...] = (),
    consumes_events: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
    feature_flag: str | None = None,
    kill_switch_required: bool = False,
    private_data_owner: str = "",
) -> CapabilitySpec:
    return CapabilitySpec(
        name=name,
        state=state,
        health=health,
        owner_domain=owner_domain,
        contract_versions=tuple(contract_versions),
        publishes_events=tuple(publishes_events),
        consumes_events=tuple(consumes_events),
        dependencies=tuple(dependencies),
        feature_flag=feature_flag,
        kill_switch_required=kill_switch_required,
        private_data_owner=private_data_owner or owner_domain,
    )


# Lifecycle here describes capability maturity, not the master execution queue.
# It must never be used to bypass queue gates or source production gates.
CAPABILITIES: dict[str, CapabilitySpec] = {
    "SIGNAL": _c(
        "SIGNAL", "ENABLED", "SIGNAL",
        contract_versions=("signal.v1",),
        publishes_events=("opportunity.updated", "signal.lifecycle_changed"),
        private_data_owner="SIGNAL",
    ),
    "EVIDENCE": _c(
        "EVIDENCE", "EXPERIMENT", "COMMAND",
        contract_versions=("evidence.v1-draft",),
        feature_flag="evidence_graph_v1",
        kill_switch_required=True,
    ),
    "OFFICE": _c(
        "OFFICE", "RESEARCH", "OFFICE",
        contract_versions=("company_state.v1-draft",),
        publishes_events=("crew.capacity_changed", "project.start_date_changed"),
        feature_flag="office_sensors",
    ),
    "DNA": _c(
        "DNA", "RESEARCH", "DNA",
        dependencies=("EVIDENCE", "OFFICE"),
        contract_versions=("outcome.v1-draft",),
        feature_flag="contractor_dna_v1",
    ),
    "SHADOW": _c(
        "SHADOW", "RESEARCH", "SHADOW",
        dependencies=("OFFICE", "DNA", "EVIDENCE"),
        contract_versions=("shadow_scenario.v1-draft",),
        feature_flag="shadow_portfolio",
        kill_switch_required=True,
    ),
    "COMMAND": _c(
        "COMMAND", "RESEARCH", "COMMAND",
        dependencies=("SIGNAL", "EVIDENCE"),
        contract_versions=("recommendation.v1-draft",),
        feature_flag="command_next_best_action",
        kill_switch_required=True,
    ),
    "ACTION": _c(
        "ACTION", "RESEARCH", "ACTION",
        dependencies=("COMMAND",),
        contract_versions=("authorized_action.v1-draft",),
        feature_flag="action_engine",
        kill_switch_required=True,
    ),
    "FUTURE_DEMAND": _c(
        "FUTURE_DEMAND", "RESEARCH", "SIGNAL",
        dependencies=("SIGNAL", "EVIDENCE"),
        feature_flag="future_demand",
    ),
    "FORCED_DEMAND": _c(
        "FORCED_DEMAND", "RESEARCH", "SIGNAL",
        dependencies=("SIGNAL", "EVIDENCE"),
        feature_flag="forced_demand",
    ),
    "UNLOCK": _c(
        "UNLOCK", "RESEARCH", "COMMAND",
        dependencies=("OFFICE", "EVIDENCE"),
        feature_flag="dynamic_eligibility",
    ),
    "SUPPLY_EDGE": _c(
        "SUPPLY_EDGE", "RESEARCH", "ACTION",
        dependencies=("SHADOW", "ACTION"),
        publishes_events=("supplier.quote_received", "material.shortage_detected"),
        feature_flag="supply_edge",
        kill_switch_required=True,
    ),
    "TRUSTBRIDGE": _c(
        "TRUSTBRIDGE", "RESEARCH", "DNA",
        dependencies=("EVIDENCE", "SUPPLY_EDGE", "ACTION"),
        feature_flag="trustbridge",
        kill_switch_required=True,
    ),
    "MOBILIZE": _c(
        "MOBILIZE", "RESEARCH", "SHADOW",
        dependencies=("OFFICE", "SHADOW", "ACTION", "SUPPLY_EDGE"),
        feature_flag="mobilize",
    ),
    "BANGS": _c(
        "BANGS", "RESEARCH", "SHADOW",
        contract_versions=("bangs.v0",),
        feature_flag="bangs_field_intelligence_v0",
        kill_switch_required=True,
        private_data_owner="BANGS",
    ),
    "SITE_READY": _c(
        "SITE_READY", "RESEARCH", "COMMAND",
        dependencies=("EVIDENCE", "OFFICE", "MOBILIZE"),
        publishes_events=("project.delay_detected",),
        feature_flag="site_ready",
    ),
    "MICROWORKS": _c(
        "MICROWORKS", "RESEARCH", "COMMAND",
        dependencies=("OFFICE", "SHADOW", "ACTION"),
        feature_flag="microworks",
        kill_switch_required=True,
    ),
}


def capability(name: str) -> CapabilitySpec:
    try:
        return CAPABILITIES[name]
    except KeyError as exc:
        raise KeyError(f"capability not registered: {name}") from exc


def enabled_capabilities() -> tuple[str, ...]:
    return tuple(sorted(name for name, spec in CAPABILITIES.items() if spec.state == "ENABLED"))


def dependency_cycles() -> tuple[tuple[str, ...], ...]:
    """Return detected dependency cycles; empty tuple is the required steady state."""
    cycles: list[tuple[str, ...]] = []
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            start = visiting.index(name)
            cycles.append(tuple(visiting[start:] + [name]))
            return
        if name in visited:
            return
        visiting.append(name)
        for dep in CAPABILITIES[name].dependencies:
            if dep in CAPABILITIES:
                visit(dep)
        visiting.pop()
        visited.add(name)

    for name in CAPABILITIES:
        visit(name)
    return tuple(cycles)


def validate_capability_registry() -> None:
    cycles = dependency_cycles()
    if cycles:
        raise RuntimeError(f"capability dependency cycle(s): {cycles}")
    for name, spec in CAPABILITIES.items():
        if spec.name != name:
            raise RuntimeError(f"capability key/name mismatch: {name}")
        unknown = set(spec.dependencies) - set(CAPABILITIES)
        if unknown:
            raise RuntimeError(f"{name} depends on unregistered capabilities: {sorted(unknown)}")
        if spec.kill_switch_required and not spec.feature_flag:
            raise RuntimeError(f"{name} requires a kill switch but has no feature flag")
        if spec.state in {"EXPERIMENT", "PILOT"} and not spec.feature_flag:
            raise RuntimeError(f"{name} experimental rollout lacks a feature flag")


validate_capability_registry()
