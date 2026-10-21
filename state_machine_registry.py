"""Observation-only state-machine registry for ObraSignal.

This module records repository-proven state semantics without becoming a second
business-policy authority.  Domain owners remain authoritative for transition
policy.  Unknown/owner-required semantics are represented explicitly rather
than guessed from enum names.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Literal

EvidenceStatus = Literal[
    "PROVEN_ALLOWED",
    "PROVEN_FORBIDDEN",
    "DISCOVERED_UNKNOWN",
    "OWNER_POLICY_REQUIRED",
    "STALE",
]


@dataclass(frozen=True)
class MachineSpec:
    machine: str
    entity: str
    owner_boundary: str
    canonical_storage: str
    state_fields: tuple[str, ...]
    derived_state: str | None
    initial_state: str
    terminal_states: tuple[str, ...]
    terminal_policy: EvidenceStatus
    unknown_state: str
    transition_writers: tuple[str, ...]
    readers: tuple[str, ...]
    side_effects: tuple[str, ...]
    temporal_inputs: tuple[str, ...]
    tenant_scope: str
    recovery_path: str
    transition_enforcement: str
    evidence_status: EvidenceStatus


STATE_REGISTRY: tuple[MachineSpec, ...] = (
    MachineSpec(
        machine="opportunity_workflow",
        entity="account-scoped opportunity pursuit",
        owner_boundary="workflow/pursuit",
        canonical_storage="opportunity_workflow.status",
        state_fields=("status",),
        derived_state=None,
        initial_state="NEW",
        # WON/LOST are excluded from the mobile active count, but current tests
        # also exercise WON -> LOST.  Do not invent terminality from labels.
        terminal_states=(),
        terminal_policy="OWNER_POLICY_REQUIRED",
        unknown_state="INVALID_STATUS_REJECTED",
        transition_writers=(
            "opportunity_workflow.set_workflow",
            "api.opportunity_workflow:POST",
        ),
        readers=(
            "opportunity_workflow.get_workflow",
            "opportunity_workflow.workflow_counts",
            "api.opportunities",
            "api.opportunity_detail",
            "mobile.components.WorkflowFunnel",
        ),
        side_effects=(),
        temporal_inputs=("updated_at",),
        tenant_scope="account_id + source + external_id",
        recovery_path="durable row; missing row is explicitly presented as NEW",
        transition_enforcement="ENUM_MEMBERSHIP_ONLY; no repository transition matrix",
        evidence_status="DISCOVERED_UNKNOWN",
    ),
    MachineSpec(
        machine="opportunity_lifecycle",
        entity="source-native opportunity actionability",
        owner_boundary="source lifecycle",
        canonical_storage="opportunity_lifecycle.is_actionable",
        state_fields=("is_actionable", "lifecycle_status"),
        derived_state="effective actionability also consumes deadline when lifecycle row is absent",
        initial_state="NO_LIFECYCLE_OBSERVATION",
        # Reopen/extension is explicitly supported by the effective-actionability
        # contract, so non-actionable is not globally terminal.
        terminal_states=(),
        terminal_policy="PROVEN_ALLOWED",
        unknown_state="ABSENT_LIFECYCLE_OR_UNPARSABLE/MISSING_DEADLINE",
        transition_writers=(
            "opportunity_lifecycle.persist_lifecycle_observations",
            "source_runtime.commit_staged_source_syncs",
        ),
        readers=(
            "opportunity_lifecycle.actionable_predicate",
            "lifecycle_read_model",
            "api.opportunities",
            "api.alerts",
            "notification_events.record_new_opportunities",
        ),
        side_effects=("commercial surfaces include/exclude opportunity",),
        temporal_inputs=("source_updated_at", "last_observed", "deadline"),
        tenant_scope="global source + external_id; consumed by account-scoped projections",
        recovery_path="source-side transaction rolls back Signal/metadata/lifecycle/cursor together",
        transition_enforcement="SOURCE_OBSERVATION_UPSERT; chronology authority is external",
        evidence_status="DISCOVERED_UNKNOWN",
    ),
    MachineSpec(
        machine="opportunity_event_ack",
        entity="account-scoped high-match opportunity event",
        owner_boundary="notification eventing",
        canonical_storage="opportunity_events.delivered_at",
        state_fields=("delivered_at",),
        derived_state="NEW when delivered_at is NULL; DELIVERED_MARKED otherwise",
        initial_state="NEW",
        terminal_states=(),
        terminal_policy="OWNER_POLICY_REQUIRED",
        unknown_state="EVENT_ABSENT",
        transition_writers=(
            "notification_events.record_new_opportunities",
            "api.alert_delivered",
        ),
        readers=("api.alerts",),
        side_effects=("client-visible alert acknowledgement marker",),
        temporal_inputs=("created_at", "delivered_at"),
        tenant_scope="account_id + event_key",
        recovery_path="event_key uniqueness deduplicates event creation",
        transition_enforcement="event creation dedupe + account-scoped ack update",
        evidence_status="DISCOVERED_UNKNOWN",
    ),
    MachineSpec(
        machine="master_execution_queue",
        entity="canonical engineering/product execution item",
        owner_boundary="engineering operations/orchestration",
        canonical_storage="master_execution_queue.MASTER_EXECUTION_QUEUE",
        state_fields=("state",),
        derived_state="dependency-ready QUEUED items",
        initial_state="OWNER_DEFINED",
        terminal_states=("DONE",),
        terminal_policy="PROVEN_ALLOWED",
        unknown_state="UNKNOWN_STATE_INVALID",
        transition_writers=("owner-authorized repository edit/promotion",),
        readers=(
            "master_execution_queue.current_item",
            "master_execution_queue.executable_after_current",
        ),
        side_effects=("changes what work may execute automatically",),
        temporal_inputs=(),
        tenant_scope="repository-global operational metadata",
        recovery_path="durable repository state; current_item fails closed unless exactly one ACTIVE",
        transition_enforcement="GATED/FUTURE never auto-promote; exactly one ACTIVE required",
        evidence_status="PROVEN_ALLOWED",
    ),
)


AUTHORITY_GRAPH: tuple[tuple[str, str, str], ...] = (
    ("api.opportunity_workflow:POST", "opportunity_workflow.set_workflow", "authenticated account command"),
    ("source_runtime.commit_staged_source_syncs", "opportunity_lifecycle.persist_lifecycle_observations", "source observation"),
    ("notification_events.record_new_opportunities", "opportunity_events", "high-match actionable event creation"),
    ("api.alert_delivered", "opportunity_events.delivered_at", "account-scoped acknowledgement mutation"),
    ("master_execution_queue.current_item", "MASTER_EXECUTION_QUEUE", "read-only invariant enforcement"),
)


IMPOSSIBLE_STATE_CANDIDATES: tuple[dict[str, str], ...] = (
    {
        "id": "WORKFLOW_TERMINAL_RESURRECTION",
        "classification": "OWNER_POLICY_REQUIRED",
        "reason": "Current repository does not prove which pursuit states, if any, are terminal.",
    },
    {
        "id": "STALE_SOURCE_LIFECYCLE_RESURRECTION",
        "classification": "DISCOVERED_UNKNOWN",
        "reason": "Ordering/chronology is not owned by this registry; consume Temporal authority before enforcement.",
    },
    {
        "id": "EVENT_ACK_EQUALS_PROVIDER_DELIVERY",
        "classification": "PROVEN_FORBIDDEN",
        "reason": "opportunity_events.delivered_at is an event acknowledgement marker, not provider-delivery authority.",
    },
)


def registry_by_name() -> dict[str, MachineSpec]:
    return {item.machine: item for item in STATE_REGISTRY}


def semantic_fingerprint() -> str:
    """Deterministic semantic fingerprint for review-required registry drift."""
    payload = {
        "machines": [asdict(item) for item in STATE_REGISTRY],
        "authority_graph": AUTHORITY_GRAPH,
        "impossible_state_candidates": IMPOSSIBLE_STATE_CANDIDATES,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_registry() -> None:
    names = [item.machine for item in STATE_REGISTRY]
    if len(names) != len(set(names)):
        raise RuntimeError("state-machine registry contains duplicate machine names")
    for item in STATE_REGISTRY:
        if not item.state_fields:
            raise RuntimeError(f"{item.machine}: state_fields must not be empty")
        if item.terminal_policy == "OWNER_POLICY_REQUIRED" and item.terminal_states:
            raise RuntimeError(f"{item.machine}: cannot invent terminal states while owner policy is required")
        if not item.unknown_state:
            raise RuntimeError(f"{item.machine}: UNKNOWN handling must be explicit")
