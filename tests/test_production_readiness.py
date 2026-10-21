from __future__ import annotations

import copy
from pathlib import Path

import pytest

from production_readiness import (
    DEFAULT_MANIFEST,
    REQUIRED_GATES,
    ReadinessContractError,
    assert_current_main,
    audit_target,
    load_manifest,
    validate_manifest,
)


EXPECTED_MAIN = "66d43f6fd51cf9cea08016dad335aaa04b711a24"


def _manifest():
    return load_manifest(DEFAULT_MANIFEST)


def _gate(manifest, gate_id):
    return next(gate for gate in manifest["gates"] if gate["id"] == gate_id)


def test_manifest_is_repository_root_and_complete():
    assert Path(DEFAULT_MANIFEST).name == "production_readiness_manifest.json"
    manifest = _manifest()
    by_id = validate_manifest(manifest)
    assert tuple(REQUIRED_GATES) == (
        "AUTH",
        "TENANT",
        "DATA",
        "SOURCES",
        "WEB",
        "MOBILE",
        "NOTIFICATIONS",
        "BILLING",
        "EVALUATION",
        "PRIVACY",
        "RECOVERY",
        "SECURITY",
        "OBSERVABILITY",
        "GOLDEN",
        "CUSTOMER_PROOF",
    )
    assert set(by_id) == set(REQUIRED_GATES)
    assert manifest["snapshot"]["canonical_main"] == EXPECTED_MAIN
    assert manifest["snapshot"]["stale_if_main_moves"] is True


def test_current_web_saas_is_truthfully_no_go():
    result = audit_target(_manifest(), "CURRENT_WEB_SAAS")
    assert result.verdict == "NO_GO"
    assert set(result.blockers) >= {
        "WEB",
        "BILLING",
        "EVALUATION",
        "PRIVACY",
        "RECOVERY",
        "SECURITY",
        "GOLDEN",
        "CUSTOMER_PROOF",
    }
    assert set(result.unknowns) >= {"TENANT", "DATA", "SOURCES", "OBSERVABILITY"}


def test_full_multi_channel_adds_mobile_and_notification_uncertainty():
    result = audit_target(_manifest(), "FULL_MULTI_CHANNEL")
    assert result.verdict == "NO_GO"
    assert "MOBILE" in result.unknowns
    assert "NOTIFICATIONS" in result.unknowns


def test_candidate_green_cannot_be_relabelled_as_release_pass():
    manifest = copy.deepcopy(_manifest())
    gate = _gate(manifest, "DATA")
    gate["classification"] = "READY"
    gate["release_gate"] = "PASS"
    gate["evidence_scope"] = "CANDIDATE_ONLY"

    with pytest.raises(ReadinessContractError, match="cannot PASS from candidate"):
        validate_manifest(manifest)


def test_unknown_defect_or_external_cannot_pass():
    for classification in ("UNKNOWN", "DEFECT", "EXTERNAL"):
        manifest = copy.deepcopy(_manifest())
        gate = _gate(manifest, "WEB")
        gate["classification"] = classification
        gate["release_gate"] = "PASS"
        gate["evidence_scope"] = "CURRENT_MAIN_ACCEPTANCE"
        with pytest.raises(ReadinessContractError, match="cannot PASS"):
            validate_manifest(manifest)


def test_one_non_pass_gate_is_enough_to_keep_no_go():
    manifest = copy.deepcopy(_manifest())
    target = "CURRENT_WEB_SAAS"
    selected = set(manifest["targets"][target])

    for gate in manifest["gates"]:
        if gate["id"] in selected:
            gate["classification"] = "READY"
            gate["release_gate"] = "PASS"
            gate["evidence_scope"] = "CURRENT_MAIN_ACCEPTANCE"

    holdout = _gate(manifest, "CUSTOMER_PROOF")
    holdout["classification"] = "UNKNOWN"
    holdout["release_gate"] = "UNKNOWN"
    holdout["evidence_scope"] = "CURRENT_MAIN_PARTIAL"
    holdout["remaining"] = ["customer proof intentionally withheld"]

    result = audit_target(manifest, target)
    assert result.verdict == "NO_GO"
    assert result.blockers == ()
    assert result.unknowns == ("CUSTOMER_PROOF",)


def test_go_requires_every_selected_gate_to_be_current_and_proven():
    manifest = copy.deepcopy(_manifest())
    target = "CURRENT_WEB_SAAS"
    selected = set(manifest["targets"][target])

    for gate in manifest["gates"]:
        if gate["id"] in selected:
            gate["classification"] = "READY"
            gate["release_gate"] = "PASS"
            gate["evidence_scope"] = "CURRENT_MAIN_ACCEPTANCE"

    result = audit_target(manifest, target)
    assert result.verdict == "GO"
    assert result.blockers == ()
    assert result.unknowns == ()


def test_main_movement_must_not_be_silently_ignored():
    manifest = copy.deepcopy(_manifest())
    manifest["snapshot"]["stale_if_main_moves"] = False
    with pytest.raises(ReadinessContractError, match="become stale when main moves"):
        validate_manifest(manifest)


def test_current_main_match_is_explicitly_accepted():
    assert_current_main(_manifest(), EXPECTED_MAIN)


def test_current_main_drift_fails_closed_until_reconstructed():
    with pytest.raises(ReadinessContractError, match="snapshot is stale"):
        assert_current_main(_manifest(), "f" * 40)


def test_blank_observed_main_is_not_accepted():
    with pytest.raises(ReadinessContractError, match="current_main_sha"):
        assert_current_main(_manifest(), "   ")


def test_inventory_cannot_drop_a_required_gate():
    manifest = copy.deepcopy(_manifest())
    manifest["gates"] = [gate for gate in manifest["gates"] if gate["id"] != "PRIVACY"]
    with pytest.raises(ReadinessContractError, match="gate inventory mismatch"):
        validate_manifest(manifest)
