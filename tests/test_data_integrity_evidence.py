import json
from pathlib import Path


def test_source_commit_drift_evidence_is_noncanonical_and_fail_closed():
    evidence_path = Path(__file__).resolve().parents[1] / "data_integrity_evidence.json"
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert payload["canonical_main_sha"] == "66d43f6fd51cf9cea08016dad335aaa04b711a24"
    item = next(
        entry for entry in payload["evidence"]
        if entry["invariant"] == "SOURCE_HEALTH_MUST_NOT_OUTLIVE_FAILED_CANONICAL_INGEST"
    )
    assert item["classification"] == "PROVEN_INTEGRATION_DRIFT_NOT_CANONICAL"
    assert item["probe"]["base_sha"].startswith("4d6acf00")
    assert item["probe"]["head_sha"].startswith("d9103c14")
    assert item["canonical_main_status"] == "UNKNOWN"
    assert item["canonical_main_claim"] == "NO_CANONICAL_DEFECT_CLAIM_FROM_NONCANONICAL_PROBE"
    assert item["repair_direction"] == "UNDEFINED_FAIL_CLOSED"
    assert item["automatic_repair"] is False


def test_source_commit_drift_keeps_owner_boundaries_explicit():
    evidence_path = Path(__file__).resolve().parents[1] / "data_integrity_evidence.json"
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    item = payload["evidence"][0]

    assert set(item["owners"]) == {
        "Source Health",
        "Persistence/Data Reliability",
        "Resilience",
        "Integration Lab",
    }
    assert "Integrity owns the invariant" in item["handoff"]
    assert "current-main-derived tree" in item["reopen_condition"]
