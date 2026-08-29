import pytest

from factory_cloud.capability_inventory import CapabilityInventoryError, capability_index, load_capability_inventory


def test_canonical_inventory_promotes_shared_core_only_with_owner_version_and_consumers():
    data = load_capability_inventory()
    index = capability_index(data)
    assert index["identity_authentication"]["state"] == "SHARED_CORE"
    assert index["persistent_execution_recovery"]["state"] == "SHARED_VERIFIED"
    core = [item for item in data["capabilities"] if item["state"] == "SHARED_CORE"]
    assert core
    for item in core:
        assert item.get("owner")
        assert item.get("version")
        assert len(item.get("verified_consumers", [])) >= 2
        assert item.get("evidence_paths")


def test_verified_capability_requires_evidence(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text('{"capabilities":[{"id":"x","layer":"shared-platform","state":"SHARED_VERIFIED","source_app":"a","evidence_paths":[],"next_proof":"p"}]}', encoding="utf-8")
    with pytest.raises(CapabilityInventoryError, match="requires evidence"):
        load_capability_inventory(path)
