from __future__ import annotations

from vertical_apps.industrial_claims.transparency import TransparencySubject, build_transparency_batch


def test_public_transparency_anchor_exposes_only_cryptographic_commitments():
    hostile_batch_id = "CLIENT=ACME / EUR=50000 / FILE=customer-change-order.pdf"
    batch = build_transparency_batch(
        (
            TransparencySubject("tenant-a", "finding-a", "a" * 64, "nonce-0123456789abcdef"),
            TransparencySubject("tenant-b", "finding-b", "b" * 64, "nonce-fedcba9876543210"),
        ),
        batch_id=hostile_batch_id,
    )
    public = batch["public_anchor_payload"]
    rendered = str(public)

    assert set(public) == {"merkle_root_sha256", "private_manifest_sha256"}
    assert len(public["merkle_root_sha256"]) == 64
    assert len(public["private_manifest_sha256"]) == 64
    assert public["private_manifest_sha256"] == batch["private_manifest_sha256"]

    # Free-form/private metadata may exist in the private manifest but can never be
    # serialized onto the external anchor surface.
    assert batch["private_manifest"]["batch_id"] == hostile_batch_id
    for secret in (
        "tenant-a",
        "tenant-b",
        "finding-a",
        "finding-b",
        "ACME",
        "50000",
        "customer-change-order.pdf",
        hostile_batch_id,
    ):
        assert secret not in rendered
