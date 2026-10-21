from concurrent.futures import ThreadPoolExecutor

from cloud_switching.sqlite_workspace import SQLiteDecisionWorkspace


def delivery_payload(tenant_id: str, sequence: int) -> dict:
    return {
        "decision": {
            "company_id": tenant_id,
            "case_id": "case-1",
            "sequence": sequence,
        },
        "options": {},
        "forecast": {},
        "outcome": None,
    }


def test_concurrent_delivery_writes_receive_unique_monotonic_versions(tmp_path):
    workspace = SQLiteDecisionWorkspace(tmp_path / "concurrent.db")

    def write(sequence: int) -> int:
        return workspace.save_delivery(
            tenant_id="tenant-a",
            package_id="case-1",
            payload=delivery_payload("tenant-a", sequence),
        ).version

    with ThreadPoolExecutor(max_workers=5) as executor:
        versions = list(executor.map(write, range(1, 11)))

    assert sorted(versions) == list(range(1, 11))
    final = workspace.load_delivery(tenant_id="tenant-a", package_id="case-1")
    assert final is not None
    assert final.version == 10
    assert 1 <= int(final.payload["decision"]["sequence"]) <= 10


def test_concurrent_writes_for_different_tenants_never_cross_contaminate(tmp_path):
    workspace = SQLiteDecisionWorkspace(tmp_path / "tenants.db")

    def write(tenant_id: str):
        workspace.save_delivery(
            tenant_id=tenant_id,
            package_id="same-id",
            payload=delivery_payload(tenant_id, 1),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(write, ("tenant-a", "tenant-b")))

    a = workspace.load_delivery(tenant_id="tenant-a", package_id="same-id")
    b = workspace.load_delivery(tenant_id="tenant-b", package_id="same-id")
    assert a is not None and b is not None
    assert a.payload["decision"]["company_id"] == "tenant-a"
    assert b.payload["decision"]["company_id"] == "tenant-b"
