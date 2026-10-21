import sqlite3


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_registry_is_well_formed_and_fingerprint_is_deterministic():
    from state_machine_registry import semantic_fingerprint, validate_registry

    validate_registry()
    first = semantic_fingerprint()
    second = semantic_fingerprint()
    assert first == second
    assert len(first) == 64
    int(first, 16)


def test_workflow_registry_tracks_repository_owner_without_inventing_terminality():
    from opportunity_workflow import STATUSES, get_workflow
    from state_machine_registry import registry_by_name

    machine = registry_by_name()["opportunity_workflow"]
    assert STATUSES == ("NEW", "REVIEWING", "PREPARING", "SUBMITTED", "WON", "LOST")
    assert machine.initial_state == "NEW"
    assert machine.terminal_states == ()
    assert machine.terminal_policy == "OWNER_POLICY_REQUIRED"
    assert "ENUM_MEMBERSHIP_ONLY" in machine.transition_enforcement

    conn = _conn()
    try:
        missing = get_workflow(conn, "tenant-a", "TED", "missing")
    finally:
        conn.close()
    assert missing["status"] == machine.initial_state


def test_workflow_observed_owner_sequence_does_not_get_reclassified_as_terminal():
    from opportunity_workflow import set_workflow
    from state_machine_registry import registry_by_name

    machine = registry_by_name()["opportunity_workflow"]
    conn = _conn()
    try:
        for state in ("REVIEWING", "PREPARING", "SUBMITTED", "WON", "LOST"):
            current = set_workflow(conn, "tenant-a", "TED", "X-1", state)
            assert current["status"] == state
    finally:
        conn.close()
    assert machine.terminal_policy == "OWNER_POLICY_REQUIRED"


def test_master_execution_queue_registry_tracks_fail_closed_owner_invariant():
    from master_execution_queue import MASTER_EXECUTION_QUEUE, current_item
    from state_machine_registry import registry_by_name

    machine = registry_by_name()["master_execution_queue"]
    assert {item.state for item in MASTER_EXECUTION_QUEUE} <= {
        "DONE", "ACTIVE", "QUEUED", "GATED", "FUTURE"
    }
    assert sum(item.state == "ACTIVE" for item in MASTER_EXECUTION_QUEUE) == 1
    assert current_item().state == "ACTIVE"
    assert machine.terminal_states == ("DONE",)
    assert "exactly one ACTIVE" in machine.transition_enforcement


def test_registry_never_claims_event_ack_is_provider_delivery():
    from state_machine_registry import IMPOSSIBLE_STATE_CANDIDATES, registry_by_name

    machine = registry_by_name()["opportunity_event_ack"]
    assert machine.derived_state == "NEW when delivered_at is NULL; DELIVERED_MARKED otherwise"
    candidate = next(
        item for item in IMPOSSIBLE_STATE_CANDIDATES
        if item["id"] == "EVENT_ACK_EQUALS_PROVIDER_DELIVERY"
    )
    assert candidate["classification"] == "PROVEN_FORBIDDEN"
