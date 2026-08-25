import copy
import json

from contract_governance import (
    COMPATIBILITY_CLASSES,
    audit,
    evaluate_snapshot,
    fingerprint,
    load_registry,
    observe_opportunity_workflow,
)


def test_registry_is_observation_only_and_not_business_authority():
    registry = load_registry()
    assert registry["authority"] == "observation_only"
    assert registry["business_authority"] == "executable_domain_owners"
    assert set(registry["compatibility_classes"]) == COMPATIBILITY_CLASSES


def test_workflow_contract_fingerprint_matches_current_canonical_surface():
    result = audit()
    assert result["fingerprint_changed"] is False, result
    assert result["unacknowledged_findings"] == [], result
    assert result["resolved_without_acknowledgement"] == [], result
    assert result["review_required"] is False, result


def test_current_workflow_auth_consumer_mismatch_is_explicit_breaking_debt():
    snapshot = observe_opportunity_workflow()
    result = audit()
    finding = {
        item["id"]: item for item in result["findings"]
    }["opportunity_workflow.auth_e2e.flat_response_parser"]

    assert snapshot["producer"]["get_shape"] == "workflow_envelope"
    assert snapshot["producer"]["tenant"] == "authenticated_account_id"
    assert snapshot["consumers"]["mobile_api"]["read"] == "raw_envelope"
    assert snapshot["consumers"]["authenticated_e2e"]["read"] == "flat_workflow_fields"
    assert finding["classification"] == "BREAKING"
    assert finding["owner"] == "Auth/#289"


def test_fingerprint_is_deterministic_and_contract_significant():
    snapshot = observe_opportunity_workflow()
    first = fingerprint(snapshot)
    second = fingerprint(copy.deepcopy(snapshot))
    assert first == second

    changed = copy.deepcopy(snapshot)
    changed["producer"]["get_shape"] = "flat_workflow_fields"
    assert fingerprint(changed) != first


def test_unacknowledged_or_resolved_contract_change_requires_review():
    registry = load_registry()
    entry = registry["contracts"]["opportunity_workflow.v1"]
    current = observe_opportunity_workflow()

    changed = copy.deepcopy(current)
    changed["producer"]["tenant"] = "client_supplied_account_id"
    evaluated = evaluate_snapshot(changed, entry)
    assert evaluated["fingerprint_changed"] is True
    assert evaluated["review_required"] is True

    repaired = copy.deepcopy(current)
    repaired["consumers"]["authenticated_e2e"]["read"] = "workflow_envelope"
    evaluated = evaluate_snapshot(repaired, entry)
    assert evaluated["resolved_without_acknowledgement"] == [
        "opportunity_workflow.auth_e2e.flat_response_parser"
    ]
    assert evaluated["review_required"] is True


def test_registry_json_is_deterministically_serializable():
    registry = load_registry()
    encoded = json.dumps(registry, sort_keys=True, separators=(",", ":"))
    assert json.loads(encoded) == registry
