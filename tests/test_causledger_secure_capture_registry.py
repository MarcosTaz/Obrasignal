from __future__ import annotations

import json
import sqlite3

import pytest

from factory_cloud.assurance_kernel import EvidenceEnvelope
from vertical_apps.industrial_claims.secure_capture_registry import (
    SecureCaptureRegistry,
    SecureCaptureRegistryError,
)


def _envelope(*, tenant="tenant-a", evidence_id="tenant-a:case:x:commercial-basis", content_hash="a" * 64, receipt="receipt-1"):
    return EvidenceEnvelope(
        evidence_id=evidence_id,
        tenant_id=tenant,
        source_type="commercial_basis",
        source_ref="po-1",
        received_at="2026-09-01T12:00:00+00:00",
        content_hash=content_hash,
        metadata={
            "capture_mode": "DIRECT_SECURE_ORIGINAL_CAPTURE",
            "raw_content_persisted": "true",
            "original_provider_receipt_ref": receipt,
            "content_sha512": "b" * 128,
            "immutability": "WORM_LOCKED",
        },
    )


def test_registry_is_idempotent_only_for_identical_capture(tmp_path):
    registry = SecureCaptureRegistry(tmp_path / "capture.sqlite3")
    evidence = _envelope()
    first = registry.record(evidence=evidence, evidence_role="commercial_basis", captured_by="actor-a")
    second = registry.record(evidence=evidence, evidence_role="commercial_basis", captured_by="actor-a")
    assert first == second
    assert registry.count(tenant_id="tenant-a") == 1
    loaded = registry.get(
        tenant_id="tenant-a",
        evidence_id=evidence.evidence_id,
        evidence_role="commercial_basis",
        source_ref="po-1",
    )
    assert loaded == evidence

    with pytest.raises(SecureCaptureRegistryError, match="collision"):
        registry.record(
            evidence=_envelope(content_hash="c" * 64),
            evidence_role="commercial_basis",
            captured_by="actor-a",
        )
    assert registry.count(tenant_id="tenant-a") == 1


def test_registry_rejects_cross_tenant_role_and_source_substitution(tmp_path):
    registry = SecureCaptureRegistry(tmp_path / "scope.sqlite3")
    evidence = _envelope()
    registry.record(evidence=evidence, evidence_role="commercial_basis", captured_by="actor-a")

    with pytest.raises(SecureCaptureRegistryError, match="not found"):
        registry.get(tenant_id="tenant-b", evidence_id=evidence.evidence_id)
    with pytest.raises(SecureCaptureRegistryError, match="role"):
        registry.get(tenant_id="tenant-a", evidence_id=evidence.evidence_id, evidence_role="event")
    with pytest.raises(SecureCaptureRegistryError, match="source reference"):
        registry.get(tenant_id="tenant-a", evidence_id=evidence.evidence_id, source_ref="po-other")


def test_registry_detects_metadata_tampering_even_after_trigger_removal(tmp_path):
    database = tmp_path / "tamper.sqlite3"
    registry = SecureCaptureRegistry(database)
    evidence = _envelope()
    registry.record(evidence=evidence, evidence_role="commercial_basis", captured_by="actor-a")

    with sqlite3.connect(database) as conn:
        conn.execute("DROP TRIGGER causledger_secure_capture_no_update")
        row = conn.execute(
            "SELECT metadata_json FROM causledger_secure_capture_envelopes WHERE evidence_id=?",
            (evidence.evidence_id,),
        ).fetchone()
        metadata = json.loads(row[0])
        metadata["raw_content_persisted"] = "false"
        conn.execute(
            "UPDATE causledger_secure_capture_envelopes SET metadata_json=? WHERE evidence_id=?",
            (json.dumps(metadata, sort_keys=True, separators=(",", ":")), evidence.evidence_id),
        )
        conn.commit()

    with pytest.raises(SecureCaptureRegistryError, match="metadata hash mismatch"):
        registry.get(tenant_id="tenant-a", evidence_id=evidence.evidence_id)
