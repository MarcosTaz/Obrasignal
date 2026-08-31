from __future__ import annotations

import sqlite3

import pytest

from vertical_apps.industrial_claims.proof import build_proof_manifest, verify_proof_manifest
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.public_verification import build_public_receipt
from vertical_apps.industrial_claims.public_verification_store import (
    PublicVerificationStore,
    PublicVerificationStoreError,
)


class Evidence:
    evidence_id = "tenant:e1"
    source_type = "email"
    source_ref = "message:1"
    received_at = "2026-08-31T22:00:00+00:00"
    _digests = dual_digest(b"evidence")
    content_hash = _digests["sha256"]
    metadata = {
        "content_sha512": _digests["sha512"],
        "content_size_bytes": _digests["byte_length"],
        "raw_content_persisted": "false",
        "source_authentication": "UNVERIFIED",
        "time_attestation": "LOCAL_SERVER_ONLY",
        "immutability": "NOT_PROVEN",
    }


def _pack():
    core = {"tenant_id": "tenant", "finding": {"finding_id": "tenant:f1"}}
    manifest = build_proof_manifest(
        core_package=core,
        evidence=(Evidence(),),
        revision_number=1,
        supersedes_finding_id=None,
        generated_at="2026-08-31T22:05:00+00:00",
    )
    verification = verify_proof_manifest(core, manifest)
    return {
        "proof_manifest": manifest,
        "self_verification": verification,
        "external_verification_required": True,
    }


def _receipt(token: str):
    return build_public_receipt(
        _pack(),
        verification_id=token,
        issued_at="2026-08-31T22:10:00+00:00",
    )


def test_public_registry_returns_no_private_scope(tmp_path):
    store = PublicVerificationStore(tmp_path / "proof.db")
    token = "A" * 32
    store.publish(
        tenant_id="private-tenant",
        subject_ref="private-finding",
        receipt=_receipt(token),
        actor_id="operator",
    )
    public = store.get_public(token)
    rendered = repr(public)
    assert "private-tenant" not in rendered
    assert "private-finding" not in rendered
    assert public["current_lifecycle"]["state"] == "CURRENT"


def test_supersession_is_append_only_and_cross_tenant_is_rejected(tmp_path):
    database = tmp_path / "proof.db"
    store = PublicVerificationStore(database)
    old = "B" * 32
    new = "C" * 32
    other = "D" * 32
    store.publish(tenant_id="tenant-a", subject_ref="f1", receipt=_receipt(old), actor_id="operator")
    store.publish(tenant_id="tenant-a", subject_ref="f2", receipt=_receipt(new), actor_id="operator")
    store.publish(tenant_id="tenant-b", subject_ref="f3", receipt=_receipt(other), actor_id="operator")

    with pytest.raises(PublicVerificationStoreError, match="does not belong"):
        store.transition(
            tenant_id="tenant-b",
            verification_id=old,
            event_id="event-owner",
            event_type="WITHDRAWN",
            reason="wrong tenant operator",
            actor_id="operator-b",
        )

    with pytest.raises(PublicVerificationStoreError, match="cross-tenant"):
        store.transition(
            tenant_id="tenant-a",
            verification_id=old,
            event_id="event-cross",
            event_type="SUPERSEDED",
            successor_verification_id=other,
            reason="wrong tenant successor",
            actor_id="operator",
        )

    store.transition(
        tenant_id="tenant-a",
        verification_id=old,
        event_id="event-1",
        event_type="SUPERSEDED",
        successor_verification_id=new,
        reason="corrected proof package",
        actor_id="operator",
    )
    public = store.get_public(old)
    assert public["current_lifecycle"]["state"] == "SUPERSEDED"
    assert public["current_lifecycle"]["event_chain_head_sha256"]

    with pytest.raises(PublicVerificationStoreError, match="terminal"):
        store.transition(
            tenant_id="tenant-a",
            verification_id=old,
            event_id="event-2",
            event_type="WITHDRAWN",
            reason="second terminal transition",
            actor_id="operator",
        )

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with sqlite3.connect(database) as conn:
            conn.execute("UPDATE causledger_public_receipts SET actor_id='attacker'")


def test_tampered_public_receipt_storage_fails_closed(tmp_path):
    database = tmp_path / "proof.db"
    store = PublicVerificationStore(database)
    token = "E" * 32
    store.publish(tenant_id="tenant", subject_ref="f", receipt=_receipt(token), actor_id="operator")
    with sqlite3.connect(database) as conn:
        conn.execute("DROP TRIGGER causledger_public_receipts_no_update")
        conn.execute("UPDATE causledger_public_receipts SET receipt_sha256=?", ("0" * 64,))
    with pytest.raises(PublicVerificationStoreError, match="integrity"):
        store.get_public(token)
