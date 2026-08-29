import json

import pytest

from factory_cloud.capability_inventory import CapabilityInventoryError, capability_index, load_capability_inventory


def test_canonical_inventory_promotes_only_evidenced_multi_consumer_core():
    data = load_capability_inventory()
    index = capability_index(data)
    assert index["identity_authentication"]["state"] == "SHARED_CORE"
    assert len(index["identity_authentication"]["verified_consumers"]) >= 2
    assert index["identity_authentication"]["owner"] == "factory-cloud/shared-platform"
    # Code/tests alone are not enough to claim deployed persistent execution.
    assert index["persistent_execution_recovery"]["state"] == "SHARED_CONTRACT_PROPOSED"
    assert index["persistent_execution_recovery"]["verified_consumers"] == []
    for item in data["capabilities"]:
        if item["state"] == "SHARED_CORE":
            assert item["evidence_paths"]
            assert len(item["verified_consumers"]) >= 2
            assert item["owner"]


def test_verified_capability_requires_evidence_and_two_consumers(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"capabilities":[{"id":"x","layer":"shared-platform","state":"SHARED_VERIFIED","source_app":"a","evidence_paths":[],"verified_consumers":[],"next_proof":"p"}]}), encoding="utf-8")
    with pytest.raises(CapabilityInventoryError, match="requires evidence"):
        load_capability_inventory(path)


def test_shared_core_requires_owner(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"capabilities":[{"id":"x","layer":"shared-platform","state":"SHARED_CORE","source_app":"a","evidence_paths":["x.py"],"verified_consumers":["a","b"],"next_proof":"p"}]}), encoding="utf-8")
    with pytest.raises(CapabilityInventoryError, match="requires owner"):
        load_capability_inventory(path)
