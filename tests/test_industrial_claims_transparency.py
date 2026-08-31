from __future__ import annotations

from vertical_apps.industrial_claims.transparency import TransparencySubject, build_transparency_batch


def test_public_transparency_anchor_does_not_disclose_tenant_or_subject():
    batch = build_transparency_batch(
        (
            TransparencySubject("tenant-a", "finding-a", "a" * 64, "nonce-0123456789abcdef"),
            TransparencySubject("tenant-b", "finding-b", "b" * 64, "nonce-fedcba9876543210"),
        ),
        batch_id="CL-ANCHOR-2026-08-31-001",
    )
    public = batch["public_anchor_payload"]
    rendered = str(public)
    assert public["leaf_count"] == 2
    assert len(public["merkle_root_sha256"]) == 64
    assert "tenant-a" not in rendered
    assert "finding-a" not in rendered
    assert public["contains_customer_or_tenant_identifiers"] is False
