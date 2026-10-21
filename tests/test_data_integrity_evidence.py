import json
from pathlib import Path


def _evidence():
    evidence_path = Path(__file__).resolve().parents[1] / "data_integrity_evidence.json"
    return json.loads(evidence_path.read_text(encoding="utf-8"))


def test_source_commit_drift_evidence_is_noncanonical_and_fail_closed():
    payload = _evidence()

    assert payload["canonical_main_sha"] == "66d43f6fd51cf9cea08016dad335aaa04b711a24"
    item = next(
        entry for entry in payload["evidence"]
        if entry["invariant"] == "SOURCE_HEALTH_MUST_NOT_OUTLIVE_FAILED_CANONICAL_INGEST"
    )
    assert item["classification"] == "PROVEN_INTEGRATION_DRIFT_NOT_CANONICAL"
    assert item["probe"]["base_sha"].startswith("4d6acf00")
    assert item["probe"]["head_sha"].startswith("d9103c14")
    assert item["probe"]["quality_run_id"] == 32899455353
    assert item["probe"]["quality_conclusion"] == "failure"
    assert item["canonical_main_status"] == "UNKNOWN"
    assert item["canonical_main_claim"] == "NO_CANONICAL_DEFECT_CLAIM_FROM_NONCANONICAL_PROBE"
    assert item["repair_direction"] == "UNDEFINED_FAIL_CLOSED"
    assert item["automatic_repair"] is False
    assert item["routed"]["source_health_comment_id"] == 5417036202


def test_source_commit_drift_keeps_owner_boundaries_explicit():
    payload = _evidence()
    item = next(
        entry for entry in payload["evidence"]
        if entry["invariant"] == "SOURCE_HEALTH_MUST_NOT_OUTLIVE_FAILED_CANONICAL_INGEST"
    )

    assert set(item["owners"]) == {
        "Source Health",
        "Persistence/Data Reliability",
        "Resilience",
        "Integration Lab",
    }
    assert "Integrity owns the invariant" in item["handoff"]
    assert "current-main-derived tree" in item["reopen_condition"]


def test_composed_source_health_migration_registration_drift_is_separate_evidence():
    payload = _evidence()
    item = next(
        entry for entry in payload["evidence"]
        if entry["invariant"] == "ADDITIVE_MIGRATION_MUST_BE_REGISTERED_ON_COMPOSED_TREE"
    )

    assert item["classification"] == "PROVEN_INTEGRATION_DRIFT_NOT_CANONICAL"
    assert item["severity"] == "HIGH"
    assert item["probe"]["quality_run_id"] == 32899455353
    assert item["probe"]["failing_test"].endswith(
        "test_root_persistence_owners_and_alters_must_be_registered"
    )
    assert item["canonical_main_status"] == "UNKNOWN"
    assert item["authority"] == "Persistence registration contract"
    assert item["repair_direction"] == "REGISTER_CLASSIFY_ON_OWNER_COMPOSITION_DO_NOT_WEAKEN_GUARD"
    assert item["automatic_repair"] is False
    assert item["routed"]["persistence_comment_id"] == 5417034789
