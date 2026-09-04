import os

import pytest

from factories.capacity_commitment.evidence_vault import (
    EvidenceVault,
    decode_evidence_key,
    generate_evidence_key,
)


def vault(tmp_path):
    return EvidenceVault(str(tmp_path / "vault"), b"k" * 32)


def test_vault_encrypts_roundtrips_and_is_idempotent(tmp_path):
    store = vault(tmp_path)
    raw = b"synthetic confidential contract bytes"
    first = store.store(tenant_id="tenant-a", evidence_id="contract-1", content=raw)
    second = store.store(tenant_id="tenant-a", evidence_id="contract-1", content=raw)
    assert first == second
    assert store.read(
        tenant_id="tenant-a", evidence_id="contract-1", expected_sha256=first.sha256
    ) == raw
    object_path = store._path("tenant-a", "contract-1")
    encrypted = object_path.read_bytes()
    assert raw not in encrypted
    if os.name == "posix":
        assert oct(object_path.stat().st_mode & 0o777) == "0o600"


def test_vault_rejects_changed_content_under_same_immutable_identity(tmp_path):
    store = vault(tmp_path)
    store.store(tenant_id="tenant-a", evidence_id="contract-1", content=b"first")
    with pytest.raises(FileExistsError, match="different identity or content"):
        store.store(tenant_id="tenant-a", evidence_id="contract-1", content=b"second")


def test_vault_tenant_identity_is_bound_into_storage_and_aad(tmp_path):
    store = vault(tmp_path)
    saved = store.store(tenant_id="tenant-a", evidence_id="same-id", content=b"tenant a")
    assert store.exists(tenant_id="tenant-a", evidence_id="same-id") is True
    assert store.exists(tenant_id="tenant-b", evidence_id="same-id") is False
    with pytest.raises(KeyError):
        store.read(tenant_id="tenant-b", evidence_id="same-id", expected_sha256=saved.sha256)


def test_wrong_key_and_tampering_fail_authentication(tmp_path):
    store = vault(tmp_path)
    saved = store.store(tenant_id="tenant-a", evidence_id="contract-1", content=b"secret")
    wrong = EvidenceVault(str(tmp_path / "vault"), b"z" * 32)
    with pytest.raises(RuntimeError, match="authentication failed"):
        wrong.read(tenant_id="tenant-a", evidence_id="contract-1", expected_sha256=saved.sha256)

    path = store._path("tenant-a", "contract-1")
    payload = bytearray(path.read_bytes())
    payload[-1] ^= 1
    path.write_bytes(payload)
    with pytest.raises(RuntimeError, match="authentication failed"):
        store.read(tenant_id="tenant-a", evidence_id="contract-1", expected_sha256=saved.sha256)


def test_expected_hash_identity_mismatch_fails_before_decryption(tmp_path):
    store = vault(tmp_path)
    store.store(tenant_id="tenant-a", evidence_id="contract-1", content=b"secret")
    with pytest.raises(RuntimeError, match="hash identity mismatch"):
        store.read(tenant_id="tenant-a", evidence_id="contract-1", expected_sha256="0" * 64)


def test_vault_rejects_path_traversal_and_empty_content(tmp_path):
    store = vault(tmp_path)
    with pytest.raises(ValueError, match="unsupported characters"):
        store.store(tenant_id="../tenant", evidence_id="contract-1", content=b"x")
    with pytest.raises(ValueError, match="unsupported characters"):
        store.store(tenant_id="tenant-a", evidence_id="../contract", content=b"x")
    with pytest.raises(ValueError, match="empty"):
        store.store(tenant_id="tenant-a", evidence_id="contract-1", content=b"")


def test_environment_key_format_roundtrip_and_invalid_length():
    encoded = generate_evidence_key()
    decoded = decode_evidence_key(encoded)
    assert len(decoded) == 32
    with pytest.raises(ValueError, match="exactly 32 bytes"):
        decode_evidence_key("YWJj")
