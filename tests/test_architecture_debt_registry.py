import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "architecture" / "architecture_debt.json"
REQUIRED_FIELDS = {
    "id",
    "module",
    "owner",
    "violation",
    "blast_radius",
    "customer_risk",
    "change_frequency",
    "proof",
    "repair_path",
    "status",
}


def test_architecture_debt_registry_is_machine_readable_and_complete():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert len(payload["baseline_main_sha"]) == 40

    items = payload["items"]
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids))
    assert all(item.keys() >= REQUIRED_FIELDS for item in items)
    assert all(item["proof"] for item in items)
    assert all(item["status"] for item in items)
