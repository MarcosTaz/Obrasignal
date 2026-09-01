from __future__ import annotations

import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.offline_export_bundle import (
    OfflineOriginal,
    build_durable_offline_verification_export_bundle,
    build_offline_verification_export_bundle,
    read_durable_originals_for_offline_export,
)
from vertical_apps.industrial_claims.proof import ExternalAttestation, build_proof_manifest


PAYLOAD_A = b"customer change request original bytes"
PAYLOAD_B = b"supplier cost schedule original bytes"


def _evidence(evidence_id: str, payload: bytes):
    return SimpleNamespace(
        evidence_id=evidence_id,
        source_type="DOCUMENT",
        source_ref=f"{evidence_id}.pdf",
        received_at="2026-09-01T15:00:00+00:00",
        content_hash=hashlib.sha256(payload).hexdigest(),
        metadata={
            "content_sha512": hashlib.sha512(payload).hexdigest(),
            "content_size_bytes": len(payload),
            "raw_content_persisted": "TRUE",
            "capture_mode": "SECURE_ORIGINAL_CAPTURE",
            "source_authentication": "DIRECT_SOURCE_CAPTURE",
        },
    )


def _pack(*, attestations=()):
    core = {
        "tenant_id": "tenant-a",
        "finding": {"finding_id": "finding-a", "claim_family": "NRE"},
        "truth_boundary": {"recoverability_established": False},
    }
    manifest = build_proof_manifest(
        core_package=core,
        evidence=(_evidence("evidence-a", PAYLOAD_A), _evidence("evidence-b", PAYLOAD_B)),
        revision_number=1,
        supersedes_finding_id=None,
        attestations=attestations,
        generated_at="2026-09-01T16:00:00+00:00",
    )
    return {"core_package": core, "proof_manifest": manifest}


def _originals():
    return [OfflineOriginal("evidence-a", PAYLOAD_A), OfflineOriginal("evidence-b", PAYLOAD_B)]


class DurableOriginalStore:
    name = "worm-a"

    def __init__(self, payloads=None):
        self.payloads = payloads or {"evidence-a": PAYLOAD_A, "evidence-b": PAYLOAD_B}
        self.reads = []

    def read_immutable_version(self, *, tenant_id, evidence_id, object_ref, version_ref):
        self.reads.append((tenant_id, evidence_id, object_ref, version_ref))
        return self.payloads[evidence_id]


def _durable_service(tmp_path, *, raw_persisted=True, provider="worm-a"):
    database = tmp_path / "claims.sqlite3"
    with sqlite3.connect(database) as conn:
        conn.execute(
            "CREATE TABLE evidence (tenant_id TEXT NOT NULL, evidence_id TEXT NOT NULL, content_hash TEXT NOT NULL, metadata_json TEXT NOT NULL)"
        )
        for evidence_id, payload in (("evidence-a", PAYLOAD_A), ("evidence-b", PAYLOAD_B)):
            metadata = {
                "raw_content_persisted": raw_persisted,
                "original_store_provider": provider,
                "original_object_ref": f"obj/{evidence_id}",
                "original_version_ref": f"v/{evidence_id}",
            }
            conn.execute(
                "INSERT INTO evidence(tenant_id,evidence_id,content_hash,metadata_json) VALUES(?,?,?,?)",
                ("tenant-a", evidence_id, hashlib.sha256(payload).hexdigest(), json.dumps(metadata)),
            )
        conn.commit()
    return SimpleNamespace(store=SimpleNamespace(path=database))


def test_confidential_export_carries_every_exact_original_and_preflights_offline_verifier():
    pack = _pack()
    bundle = build_offline_verification_export_bundle(pack, originals=_originals())

    assert bundle["confidential"] is True
    assert bundle["truth_boundaries"]["contains_raw_original_bytes"] is True
    assert bundle["truth_boundaries"]["must_not_be_published"] is True
    assert set(bundle["offline_evidence"]) == {"evidence-a", "evidence-b"}
    assert bundle["independent_verification"]["valid"] is True
    assert bundle["independent_verification"]["independently_verifiable_without_causledger"] is True
    assert "offline_evidence" not in pack


def test_confidential_export_refuses_if_any_committed_original_is_missing():
    with pytest.raises(AssuranceStoreError, match="original bytes are unavailable for: evidence-b"):
        build_offline_verification_export_bundle(
            _pack(),
            originals=[OfflineOriginal("evidence-a", PAYLOAD_A)],
        )


def test_confidential_export_refuses_tampered_original_bytes():
    with pytest.raises(AssuranceStoreError, match="sha256 mismatch for evidence-a"):
        build_offline_verification_export_bundle(
            _pack(),
            originals=[OfflineOriginal("evidence-a", b"tampered"), OfflineOriginal("evidence-b", PAYLOAD_B)],
        )


def test_confidential_export_refuses_unknown_or_duplicate_originals():
    with pytest.raises(AssuranceStoreError, match="not part of this proof pack"):
        build_offline_verification_export_bundle(
            _pack(),
            originals=_originals() + [OfflineOriginal("other-case", b"secret")],
        )
    with pytest.raises(AssuranceStoreError, match="original is duplicated"):
        build_offline_verification_export_bundle(
            _pack(),
            originals=_originals() + [OfflineOriginal("evidence-a", PAYLOAD_A)],
        )


def test_durable_export_reads_only_persisted_tenant_scoped_immutable_versions(tmp_path):
    service = _durable_service(tmp_path)
    store = DurableOriginalStore()
    originals = read_durable_originals_for_offline_export(
        service=service,
        proof_pack=_pack(),
        original_store=store,
    )
    assert [(item.evidence_id, item.content) for item in originals] == [
        ("evidence-a", PAYLOAD_A),
        ("evidence-b", PAYLOAD_B),
    ]
    assert store.reads == [
        ("tenant-a", "evidence-a", "obj/evidence-a", "v/evidence-a"),
        ("tenant-a", "evidence-b", "obj/evidence-b", "v/evidence-b"),
    ]

    bundle = build_durable_offline_verification_export_bundle(
        service=service,
        proof_pack=_pack(),
        original_store=store,
    )
    assert bundle["independent_verification"]["valid"] is True


def test_durable_export_refuses_hash_only_or_wrong_provider_metadata(tmp_path):
    with pytest.raises(AssuranceStoreError, match="were not durably persisted"):
        read_durable_originals_for_offline_export(
            service=_durable_service(tmp_path / "not-persisted", raw_persisted=False),
            proof_pack=_pack(),
            original_store=DurableOriginalStore(),
        )

    with pytest.raises(AssuranceStoreError, match="provider mismatch"):
        read_durable_originals_for_offline_export(
            service=_durable_service(tmp_path / "wrong-provider", provider="other-store"),
            proof_pack=_pack(),
            original_store=DurableOriginalStore(),
        )


def test_durable_export_refuses_store_bytes_that_drift_from_manifest(tmp_path):
    store = DurableOriginalStore(payloads={"evidence-a": b"tampered", "evidence-b": PAYLOAD_B})
    with pytest.raises(AssuranceStoreError, match="sha256 mismatch for evidence-a"):
        read_durable_originals_for_offline_export(
            service=_durable_service(tmp_path),
            proof_pack=_pack(),
            original_store=store,
        )


def test_verified_external_receipt_requires_independent_verifier_before_export():
    attestation = ExternalAttestation(
        kind="EVIDENCE_ESCROW",
        provider="independent-escrow",
        state="VERIFIED",
        digest_algorithm="SHA-256",
        digest=hashlib.sha256(PAYLOAD_A).hexdigest(),
        provider_ref="escrow-receipt-a",
        issued_at="2026-09-01T15:30:00+00:00",
        validation_ref="escrow-validation-a",
        details={
            "evidence_id": "evidence-a",
            "subject_ref": "finding-a",
            "purpose": "INDEPENDENT_ORIGINAL_EVIDENCE_ESCROW",
        },
    )
    pack = _pack(attestations=(attestation,))

    with pytest.raises(AssuranceStoreError, match="EXTERNAL_VERIFIER_MISSING"):
        build_offline_verification_export_bundle(pack, originals=_originals())

    bundle = build_offline_verification_export_bundle(
        pack,
        originals=_originals(),
        external_verifiers={
            "EVIDENCE_ESCROW": lambda receipt, context: (
                receipt["provider_ref"] == "escrow-receipt-a"
                and context["evidence_id"] == "evidence-a"
                and context["expected_digest"] == hashlib.sha256(PAYLOAD_A).hexdigest()
            )
        },
    )
    assert bundle["independent_verification"]["external_attestations"]["independently_checked_count"] == 1
    assert bundle["independent_verification"]["valid"] is True
