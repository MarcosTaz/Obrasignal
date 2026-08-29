import json

import pytest

from factory_cloud.shared_core import SharedCoreError, load_shared_core


def test_shared_core_manifest_has_versioned_multi_consumer_contracts():
    manifest = load_shared_core()
    assert manifest["owner"] == "factory-cloud/shared-platform"
    assert "identity_authentication" in manifest["capabilities"]
    assert set(manifest["capabilities"]["identity_authentication"]["consumers"]) == {
        "aviation-lease-entitlement-recovery",
        "contractcredit",
    }


def test_shared_core_rejects_single_consumer(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "owner": "owner",
        "compatibility_policy": "policy",
        "capabilities": {
            "x": {"version": "1.0.0", "module": "m", "consumers": ["one"]}
        },
    }), encoding="utf-8")
    with pytest.raises(SharedCoreError, match="two consumers"):
        load_shared_core(path)
