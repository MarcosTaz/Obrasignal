import pytest

from factory_cloud.capability_inventory import CapabilityInventoryError, capability_index, load_capability_inventory


def test_canonical_inventory_is_not_prematurely_shared_core():
    data = load_capability_inventory()
    index = capability_index(data)
    assert index["identity_authentication"]["state"] == "CANDIDATE_SHARED"
    assert index["persistent_execution_recovery"]["state"] == "SHARED_CONTRACT_PROPOSED"
    assert all(item["state"] != "SHARED_CORE" for item in data["capabilities"])


def test_verified_capability_requires_evidence(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text('{"capabilities":[{"id":"x","layer":"shared-platform","state":"SHARED_VERIFIED","source_app":"a","evidence_paths":[],"next_proof":"p"}]}', encoding="utf-8")
    with pytest.raises(CapabilityInventoryError, match="requires evidence"):
        load_capability_inventory(path)
