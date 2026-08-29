import pytest

from factory_cloud.document_store import DocumentStore, DocumentStoreError


def test_document_store_is_tenant_scoped_content_addressed_and_idempotent(tmp_path):
    store = DocumentStore(tmp_path / "documents")
    first = store.put(
        tenant_id="alpha",
        document_id="contract-1",
        source_ref="msa-1",
        original_name="contract.pdf",
        content=b"contract bytes",
    )
    replay = store.put(
        tenant_id="alpha",
        document_id="contract-1",
        source_ref="msa-1",
        original_name="contract.pdf",
        content=b"contract bytes",
    )
    assert replay == first
    record, payload = store.get(tenant_id="alpha", document_id="contract-1")
    assert record.content_hash == first.content_hash
    assert payload == b"contract bytes"
    assert len(store.list(tenant_id="alpha")) == 1


def test_same_document_id_isolated_between_tenants(tmp_path):
    store = DocumentStore(tmp_path / "documents")
    alpha = store.put(tenant_id="alpha", document_id="doc-1", source_ref="a", original_name="a.txt", content=b"alpha")
    beta = store.put(tenant_id="beta", document_id="doc-1", source_ref="b", original_name="b.txt", content=b"beta")
    assert alpha.content_hash != beta.content_hash
    assert store.get(tenant_id="alpha", document_id="doc-1")[1] == b"alpha"
    assert store.get(tenant_id="beta", document_id="doc-1")[1] == b"beta"


def test_document_id_collision_and_cross_tenant_read_fail_closed(tmp_path):
    store = DocumentStore(tmp_path / "documents")
    store.put(tenant_id="alpha", document_id="doc-1", source_ref="a", original_name="a.txt", content=b"one")
    with pytest.raises(DocumentStoreError, match="immutable"):
        store.put(tenant_id="alpha", document_id="doc-1", source_ref="a", original_name="a.txt", content=b"two")
    with pytest.raises(DocumentStoreError, match="tenant-scoped"):
        store.get(tenant_id="beta", document_id="doc-1")


def test_object_corruption_is_detected(tmp_path):
    store = DocumentStore(tmp_path / "documents")
    record = store.put(tenant_id="alpha", document_id="doc-1", source_ref="a", original_name="a.txt", content=b"one")
    object_path = store._object_path(record.content_hash)
    object_path.write_bytes(b"tampered")
    with pytest.raises(DocumentStoreError, match="integrity"):
        store.get(tenant_id="alpha", document_id="doc-1")
