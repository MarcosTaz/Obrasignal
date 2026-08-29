import json

import pytest

from factory_cloud.pilot_safe_evidence import PilotSafeEvidenceError, load_evidence_manifest, passing_tokens

SHA = "a" * 40


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _policy(path):
    _write(path, {
        "evidence_contracts": {
            "billing_sandbox": {"required_proofs": ["provider_test_mode", "test_settlement", "reconciliation", "live_authority_false"]}
        }
    })


def _manifest(status="PASS", proofs=None):
    return {
        "factory_id": "contractcredit",
        "exact_source_head": SHA,
        "evidence": {
            "billing_sandbox": {
                "status": status,
                "refs": ["provider:test:invoice"] if status == "PASS" else [],
                "proofs": list(proofs or []),
            }
        },
    }


def test_critical_pass_is_rejected_when_subproofs_are_missing(tmp_path):
    policy = tmp_path / "policy.json"
    manifest = tmp_path / "manifest.json"
    _policy(policy)
    _write(manifest, _manifest(proofs=["provider_test_mode", "live_authority_false"]))
    with pytest.raises(PilotSafeEvidenceError, match="critical PASS missing required subproofs"):
        load_evidence_manifest(manifest, policy_path=policy)


def test_critical_pass_requires_every_subproof_before_token_can_pass(tmp_path):
    policy = tmp_path / "policy.json"
    manifest = tmp_path / "manifest.json"
    _policy(policy)
    proofs = ["provider_test_mode", "test_settlement", "reconciliation", "live_authority_false"]
    _write(manifest, _manifest(proofs=proofs))
    payload = load_evidence_manifest(manifest, policy_path=policy)
    assert "billing_sandbox" in passing_tokens(payload)


def test_unknown_critical_evidence_can_record_partial_proofs_without_promotion(tmp_path):
    policy = tmp_path / "policy.json"
    manifest = tmp_path / "manifest.json"
    _policy(policy)
    payload = _manifest(status="UNKNOWN", proofs=["provider_test_mode"])
    payload["evidence"]["billing_sandbox"]["refs"] = ["provider:test:invoice"]
    _write(manifest, payload)
    loaded = load_evidence_manifest(manifest, policy_path=policy)
    assert "billing_sandbox" not in passing_tokens(loaded)


def test_canonical_policy_requires_settlement_and_reconciliation_for_billing_pass(tmp_path):
    manifest = tmp_path / "manifest.json"
    payload = {
        "factory_id": "contractcredit",
        "exact_source_head": SHA,
        "evidence": {
            "billing_sandbox": {
                "status": "PASS",
                "refs": ["stripe:test:invoice"],
                "proofs": ["provider_test_mode", "synthetic_invoice_or_checkout", "live_authority_false"],
            }
        },
    }
    _write(manifest, payload)
    with pytest.raises(PilotSafeEvidenceError, match="test_settlement"):
        load_evidence_manifest(manifest)
