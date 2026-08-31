from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from vertical_apps.industrial_claims.proof import (
    ExternalAttestation,
    build_proof_manifest,
    evidence_assurance_state,
    verify_proof_manifest,
)
from vertical_apps.industrial_claims.proof_extensions import (
    CausalEdge,
    adverse_evidence_register,
    build_causal_graph,
    build_evidence_certificate,
    dual_digest,
    signed_semantic_diff_payload,
)
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle, ProofRequest
from vertical_apps.industrial_claims.proof_store import IndustrialProofStore, ProofLedgerError


def _evidence(evidence_id: str, payload: bytes):
    digests = dual_digest(payload)
    return SimpleNamespace(
        evidence_id=evidence_id,
        source_type="email",
        source_ref=f"source:{evidence_id}",
        received_at="2026-08-31T20:00:00+00:00",
        content_hash=digests["sha256"],
        metadata={
            "content_sha512": digests["sha512"],
            "content_size_bytes": digests["byte_length"],
            "raw_content_persisted": "false",
            "source_authentication": "UNVERIFIED",
            "time_attestation": "LOCAL_SERVER_ONLY",
            "immutability": "NOT_PROVEN",
        },
    )


def test_manifest_self_verifies_and_detects_package_tampering():
    evidence = (_evidence("tenant:e1", b"original-one"), _evidence("tenant:e2", b"original-two"))
    core = {"tenant_id": "tenant", "finding": {"finding_id": "tenant:f1"}, "net_potential": "100"}
    manifest = build_proof_manifest(
        core_package=core,
        evidence=evidence,
        revision_number=1,
        supersedes_finding_id=None,
        generated_at="2026-08-31T20:10:00+00:00",
    )
    verified = verify_proof_manifest(core, manifest)
    assert verified["valid"] is True
    assert manifest["dual_hash_coverage"] == {"sha256": True, "sha512": True}
    assert manifest["assurance_summary"]["weakest_evidence_state"] == "UNVERIFIED"
    assert manifest["required_external_gates"]["qualified_timestamp"] is True

    tampered = dict(core)
    tampered["net_potential"] = "101"
    assert verify_proof_manifest(tampered, manifest)["valid"] is False


def test_external_attestation_cannot_be_marked_verified_without_provider_reference():
    with pytest.raises(ValueError, match="provider reference"):
        ExternalAttestation(
            kind="QUALIFIED_TIMESTAMP",
            provider="example",
            state="VERIFIED",
            digest_algorithm="SHA-256",
            digest="a" * 64,
        )


def test_assurance_state_is_fail_closed_and_progressive():
    state, dimensions = evidence_assurance_state({}, content_hash_present=True)
    assert state == "UNVERIFIED"
    assert dimensions["content_hash_present"] is True
    assert dimensions["integrity_sealed"] is False

    timestamp = ExternalAttestation(
        kind="QUALIFIED_TIMESTAMP",
        provider="qualified-tsa",
        state="VERIFIED",
        digest_algorithm="SHA-256",
        digest="a" * 64,
        provider_ref="tsa:1",
    )
    worm = ExternalAttestation(
        kind="WORM_LOCK",
        provider="object-store",
        state="VERIFIED",
        digest_algorithm="SHA-256",
        digest="a" * 64,
        provider_ref="worm:1",
    )
    state, dimensions = evidence_assurance_state({}, content_hash_present=True, attestations=(worm, timestamp))
    assert state == "TIME_SEALED"
    assert dimensions["time_sealed"] is True


def test_unconfigured_external_providers_never_fake_success():
    providers = ProofProviderBundle.fail_closed()
    request = ProofRequest(
        tenant_id="tenant",
        subject_ref="finding",
        digest_algorithm="SHA-256",
        digest="a" * 64,
        purpose="proof-pack",
        metadata={},
    )
    result = providers.qualified_timestamp.attest(request)
    assert result.state == "UNAVAILABLE"
    assert result.verified is False
    assert result.provider_ref is None


def test_proof_ledger_is_hash_chained_and_append_only(tmp_path):
    database = tmp_path / "proof.db"
    store = IndustrialProofStore(database)
    first = store.append_event(
        event_id="event-1",
        tenant_id="tenant",
        subject_ref="finding-1",
        event_type="EVIDENCE_CAPTURED",
        actor_id="analyst",
        payload={"evidence_id": "e1"},
        first_seen_at="2026-08-31T20:00:00+00:00",
    )
    second = store.append_event(
        event_id="event-2",
        tenant_id="tenant",
        subject_ref="finding-1",
        event_type="DECLARED_EFFECTIVE_TIME",
        actor_id="analyst",
        payload={"declared": True},
        effective_at="2026-05-01T10:00:00+01:00",
        first_seen_at="2026-08-31T20:01:00+00:00",
    )
    assert second.previous_chain_hash == first.chain_hash
    verified = store.verify_chain(tenant_id="tenant", subject_ref="finding-1")
    assert verified["valid"] is True
    assert verified["event_count"] == 2

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with sqlite3.connect(database) as conn:
            conn.execute("UPDATE industrial_proof_events SET actor_id='attacker' WHERE event_id='event-1'")

    with pytest.raises(ProofLedgerError, match="already exists"):
        store.append_event(
            event_id="event-1",
            tenant_id="tenant",
            subject_ref="finding-1",
            event_type="REPLAY",
            actor_id="analyst",
            payload={},
        )


def test_forensic_extensions_are_hash_bound():
    diff = signed_semantic_diff_payload(
        before_ref="drawing-R16",
        after_ref="drawing-R17",
        before_text="diameter=10\nmaterial=A",
        after_text="diameter=12\nmaterial=A",
    )
    assert diff["diff_sha256"]
    assert diff["before_hashes"]["sha256"] != diff["after_hashes"]["sha256"]

    graph = build_causal_graph((
        CausalEdge("REQUEST_CAUSED_CHANGE", "request-1", "change-1", ("e1",)),
        CausalEdge("CHANGE_CAUSED_WORK", "change-1", "work-1", ("e2",), state="WEAK"),
    ))
    assert graph["graph_sha256"]
    assert graph["edges"][1]["state"] == "WEAK"

    adverse = adverse_evidence_register(({"evidence_id": "e3", "reason": "price may already include engineering"},))
    assert adverse["must_not_be_silently_removed"] is True


def test_evidence_certificate_preserves_truth_boundary():
    evidence = (_evidence("tenant:e1", b"payload"),)
    core = {"tenant_id": "tenant", "finding": {"finding_id": "tenant:f1"}}
    manifest = build_proof_manifest(
        core_package=core,
        evidence=evidence,
        revision_number=1,
        supersedes_finding_id=None,
        generated_at="2026-08-31T20:10:00+00:00",
    )
    certificate = build_evidence_certificate(
        manifest=manifest,
        evidence_id="tenant:e1",
        certificate_id="CL-EV-2026-000001",
    )
    assert certificate["certificate_sha256"]
    assert certificate["integrity_truth_boundary"]["commercial_responsibility_not_determined_by_certificate"] is True
