from copy import deepcopy

from support_operations_audit import audit_manifest, load_manifest


def test_repository_support_operations_manifest_is_green():
    assert audit_manifest(load_manifest()) == []


def test_manifest_audit_detects_customer_failure_taxonomy_drift():
    manifest = deepcopy(load_manifest())
    manifest["customer_failure_classes"].remove("UNKNOWN")
    assert "customer failure taxonomy drift" in audit_manifest(manifest)


def test_manifest_audit_detects_missing_supportability_journey():
    manifest = deepcopy(load_manifest())
    manifest["journeys"] = [
        row for row in manifest["journeys"] if row["id"] != "billing"
    ]
    assert "journey supportability coverage drift" in audit_manifest(manifest)


def test_manifest_audit_detects_runbook_coverage_drift():
    manifest = deepcopy(load_manifest())
    manifest["runbook_overlays"].remove("cross_tenant_suspicion")
    assert "runbook overlay coverage drift" in audit_manifest(manifest)


def test_manifest_audit_detects_false_resolution_guard_drift():
    manifest = deepcopy(load_manifest())
    manifest["forbidden_claims"].remove("UNKNOWN_EQUALS_SUCCESS")
    assert "false-resolution guard drift" in audit_manifest(manifest)


def test_manifest_audit_does_not_crash_on_malformed_taxonomy():
    manifest = deepcopy(load_manifest())
    manifest["customer_failure_classes"] = {"unexpected": "shape"}
    assert "customer failure taxonomy drift" in audit_manifest(manifest)


def test_manifest_audit_does_not_crash_on_malformed_journey_id():
    manifest = deepcopy(load_manifest())
    manifest["journeys"][0]["id"] = ["not", "hashable"]
    failures = audit_manifest(manifest)
    assert "malformed journey id" in failures
    assert "journey supportability coverage drift" in failures


def test_manifest_audit_requires_candidate_not_canonical_status():
    manifest = deepcopy(load_manifest())
    manifest["status"] = "HEALTHY"
    assert "candidate status drift" in audit_manifest(manifest)


def test_manifest_audit_requires_exact_contract_version():
    manifest = deepcopy(load_manifest())
    manifest["contract_version"] = "support-incident-operations.v2"
    assert "support contract version drift" in audit_manifest(manifest)
