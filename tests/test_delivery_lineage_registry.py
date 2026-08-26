import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _registry():
    return json.loads((ROOT / "delivery_lineage_registry.json").read_text(encoding="utf-8"))


def test_delivery_registry_never_upgrades_provider_acceptance_to_delivery():
    registry = _registry()
    strength = registry["state_strength"]
    assert strength["receipt_provider_accepted"] == "PROVIDER_ACCEPTED_NOT_DELIVERED"
    assert strength["scheduled_local_notification"] == "SCHEDULED_NOT_DELIVERED"
    assert strength["ambiguous_crash_after_provider_accept"] == "UNKNOWN_EXTERNAL_ATTEMPT"


def test_delivery_registry_preserves_upstream_decision_event_break():
    registry = _registry()
    edges = {(row["parent"], row["child"]): row for row in registry["edges"]}
    assert edges[("opportunity_decision", "opportunity_event")]["status"] == "BROKEN"
    assert edges[("opportunity_event", "push_delivery")]["status"] == "PROVEN_PARTIAL"
    assert "DECISION_EVENT_PARENTAGE_AMBIGUOUS" in registry["open_gaps"]


def test_attempt_history_is_not_mislabeled_append_only():
    registry = _registry()
    edges = {(row["parent"], row["child"]): row for row in registry["edges"]}
    attempt = edges[("push_delivery", "provider_send_attempt")]
    assert attempt["durable"] == "LATEST_ONLY"
    assert attempt["retry_stable"] == "LOGICAL_DELIVERY_ONLY"
    assert "MUTABLE_LATEST_ONLY_ATTEMPT_HISTORY" in registry["open_gaps"]


def test_provider_ticket_parentage_stays_broken_until_unique_proof_exists():
    registry = _registry()
    edges = {(row["parent"], row["child"]): row for row in registry["edges"]}
    assert edges[("provider_send_attempt", "provider_ticket")]["status"] == "BROKEN"
    assert "PROVIDER_TICKET_PARENTAGE_NOT_UNIQUE" in registry["open_gaps"]
