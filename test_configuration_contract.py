from pathlib import Path
import re

from configuration_contract import (
    CONFIG_REGISTRY,
    MOBILE_NODE_VERSION,
    MOBILE_NODE_WORKFLOWS,
    contract_fingerprint,
)


ROOT = Path(__file__).resolve().parent


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _node_version(workflow_path: str) -> str:
    text = _read(workflow_path)
    match = re.search(r"node-version:\s*['\"]?([0-9]+(?:\.[0-9]+){0,2})", text)
    assert match, f"{workflow_path} must declare an explicit Node version"
    return match.group(1)


def test_mobile_workflows_use_one_exact_node_runtime():
    observed = {path: _node_version(path) for path in MOBILE_NODE_WORKFLOWS}
    assert set(observed.values()) == {MOBILE_NODE_VERSION}, observed


def test_mobile_sample_env_covers_registered_public_build_keys():
    sample = _read("mobile/.env.example")
    required = {
        name
        for name, contract in CONFIG_REGISTRY.items()
        if name.startswith("EXPO_PUBLIC_") and contract.visibility == "PUBLIC"
    }
    missing = sorted(name for name in required if f"{name}=" not in sample)
    assert not missing, f"mobile/.env.example is missing registered keys: {missing}"


def test_production_blueprint_declares_provider_auth_explicitly():
    render = _read("render.yaml")
    assert "- key: OBRASIGNAL_AUTH_MODE\n        value: \"provider\"" in render
    assert "- key: OBRASIGNAL_JWT_ISSUER\n        sync: false" in render


def test_registry_contains_no_secret_values():
    for contract in CONFIG_REGISTRY.values():
        assert not hasattr(contract, "value")
        assert contract.visibility in {"PUBLIC", "SECRET_NAME_ONLY"}


def test_contract_fingerprint_is_deterministic_and_secret_free_shape():
    first = contract_fingerprint()
    second = contract_fingerprint()
    assert first == second
    assert re.fullmatch(r"[0-9a-f]{64}", first)
