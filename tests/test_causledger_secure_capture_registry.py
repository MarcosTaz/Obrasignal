from __future__ import annotations

import json
import sqlite3

import pytest

from factory_cloud.assurance_kernel import EvidenceEnvelope
from vertical_apps.industrial_claims.intake_authorization import recompute_intake_authorization_scope_sha256
from vertical_apps.industrial_claims.proof import canonical_json_bytes, sha256_hex
from vertical_apps.industrial_claims.secure_capture_registry import (
    SecureCaptureRegistry,
    SecureCaptureRegistryError,
)


def _envelope(
    *,
    tenant="tenant-a",
    evidence_id="tenant-a:case:x:commercial-basis",
    content_hash="a" * 64,
    receipt="receipt-1",
    metadata_overrides=None,
):
    metadata = {
        "capture_mode": "DIRECT_SECURE_ORIGINAL_CAPTURE",
        "raw_content_persisted": "true",
        "original_provider_receipt_ref": receipt,
        "content_sha512": "b" * 128,
        "immutability": "WORM_LOCKED",
        "original_retention_until": "2036-09-01T00:00:00+00:00",
        "intake_authorization_id": "auth-1",
        "intake_case_ref": "case-x",
        "intake_purpose": "BOUNDED_HISTORICAL_RAPID_SCAN",
        "intake_evidence_role": "commercial_basis",
        "intake_authorized_at": "2026-09-01T10:00:00+00:00",
        "intake_authorization_expires_at": "2026-09-02T10:00:00+00:00",
        "intake_minimum_immutable_retention_until": "2036-09-01T00:00:00+00:00",
        "intake_authorized_evidence_roles": ["commercial_basis", "event", "cost"],
        "intake_data_terms_state": "SIGNED",
        "intake_immutable_retention_acknowledged": True,
        "intake_authorized_by_sha256": "d" * 64,
        "intake_transfer_channel_sha256": "e" * 64,
        "intake_max_bytes_per_evidence": 1_000_000,
    }
    metadata.update(dict(metadata_overrides or {}))
    metadata["intake_authorization_scope_sha256"] = recompute_intake_authorization_scope_sha256(
        metadata,
        tenant_id=tenant,
    )
    return EvidenceEnvelope(
        evidence_id=evidence_id,
        tenant_id=tenant,
        source_type="commercial_basis",
        source_ref="po-1",
        received_at="2026-09-01T12:00:00+00:00",
        content_hash=content_hash,
        metadata=metadata,
    )


def test_registry_is_idempotent_only_for_identical_authorized_capture(tmp_path):
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


def test_registry_rejects_low_level_capture_without_bounded_intake_authorization(tmp_path):
    registry = SecureCaptureRegistry(tmp_path / "unauthorized.sqlite3")
    evidence = _envelope()
    metadata = dict(evidence.metadata)
    for key in tuple(metadata):
        if key.startswith("intake_"):
            metadata.pop(key)
    unauthorized = EvidenceEnvelope(
        evidence_id=evidence.evidence_id,
        tenant_id=evidence.tenant_id,
        source_type=evidence.source_type,
        source_ref=evidence.source_ref,
        received_at=evidence.received_at,
        content_hash=evidence.content_hash,
        metadata=metadata,
    )
    with pytest.raises(SecureCaptureRegistryError, match="intake_authorization_id"):
        registry.record(
            evidence=unauthorized,
            evidence_role="commercial_basis",
            captured_by="actor-a",
        )
    assert registry.count(tenant_id="tenant-a") == 0


def test_registry_rejects_intake_role_or_tenant_namespace_mismatch(tmp_path):
    registry = SecureCaptureRegistry(tmp_path / "binding.sqlite3")
    with pytest.raises(SecureCaptureRegistryError, match="intake role binding mismatch"):
        registry.record(
            evidence=_envelope(metadata_overrides={"intake_evidence_role": "event"}),
            evidence_role="commercial_basis",
            captured_by="actor-a",
        )
    with pytest.raises(SecureCaptureRegistryError, match="outside tenant namespace"):
        registry.record(
            evidence=_envelope(evidence_id="tenant-b:case:x:commercial-basis"),
            evidence_role="commercial_basis",
            captured_by="actor-a",
        )


def test_registry_rejects_provider_retention_shorter_than_authorized_minimum(tmp_path):
    registry = SecureCaptureRegistry(tmp_path / "retention.sqlite3")
    with pytest.raises(SecureCaptureRegistryError, match="retention is shorter"):
        registry.record(
            evidence=_envelope(
                metadata_overrides={"original_retention_until": "2035-09-01T00:00:00+00:00"}
            ),
            evidence_role="commercial_basis",
            captured_by="actor-a",
        )


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


def test_registry_semantically_rejects_forged_authorization_even_if_attacker_recomputes_metadata_hash(tmp_path):
    database = tmp_path / "semantic-tamper.sqlite3"
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
        metadata["intake_data_terms_state"] = "PENDING"
        metadata_json = canonical_json_bytes(metadata).decode("utf-8")
        metadata_hash = sha256_hex(metadata_json.encode("utf-8"))
        conn.execute(
            "UPDATE causledger_secure_capture_envelopes SET metadata_json=?,metadata_sha256=? WHERE evidence_id=?",
            (metadata_json, metadata_hash, evidence.evidence_id),
        )
        conn.commit()

    with pytest.raises(SecureCaptureRegistryError, match="data terms are not cleared"):
        registry.get(tenant_id="tenant-a", evidence_id=evidence.evidence_id)


def test_registry_semantically_rejects_forged_retention_even_with_recomputed_hash(tmp_path):
    database = tmp_path / "retention-tamper.sqlite3"
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
        metadata["original_retention_until"] = "2035-09-01T00:00:00+00:00"
        metadata_json = canonical_json_bytes(metadata).decode("utf-8")
        metadata_hash = sha256_hex(metadata_json.encode("utf-8"))
        conn.execute(
            "UPDATE causledger_secure_capture_envelopes SET metadata_json=?,metadata_sha256=? WHERE evidence_id=?",
            (metadata_json, metadata_hash, evidence.evidence_id),
        )
        conn.commit()

    with pytest.raises(SecureCaptureRegistryError, match="retention is shorter"):
        registry.get(tenant_id="tenant-a", evidence_id=evidence.evidence_id)


def test_registry_rejects_scope_field_rewrite_even_if_attacker_rehashes_metadata(tmp_path):
    database = tmp_path / "scope-recompute-tamper.sqlite3"
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
        metadata["intake_authorized_by_sha256"] = "f" * 64
        metadata_json = canonical_json_bytes(metadata).decode("utf-8")
        metadata_hash = sha256_hex(metadata_json.encode("utf-8"))
        conn.execute(
            "UPDATE causledger_secure_capture_envelopes SET metadata_json=?,metadata_sha256=? WHERE evidence_id=?",
            (metadata_json, metadata_hash, evidence.evidence_id),
        )
        conn.commit()

    with pytest.raises(SecureCaptureRegistryError, match="scope hash mismatch"):
        registry.get(tenant_id="tenant-a", evidence_id=evidence.evidence_id)