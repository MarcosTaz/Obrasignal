import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "architecture" / "module_ownership.json"
ALLOWED_STATES = {"PROVEN", "MULTI_OWNER", "UNKNOWN"}
REQUIRED_FIELDS = {
    "module",
    "responsibility",
    "owner",
    "ownership_state",
    "public_surface",
    "side_effect_surface",
    "evidence",
}


def test_module_ownership_registry_is_explicit_and_machine_readable():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["default_owner"] == "UNKNOWN"
    assert len(payload["baseline_main_sha"]) == 40

    modules = payload["modules"]
    names = [item["module"] for item in modules]
    assert len(names) == len(set(names))
    assert all(item.keys() >= REQUIRED_FIELDS for item in modules)
    assert all(item["ownership_state"] in ALLOWED_STATES for item in modules)
    assert all(item["evidence"] for item in modules)


def test_unknown_ownership_is_not_silently_promoted_to_shared():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    unknown = [item for item in payload["modules"] if item["ownership_state"] == "UNKNOWN"]
    assert unknown
    assert all(item["owner"] == "UNKNOWN" for item in unknown)
