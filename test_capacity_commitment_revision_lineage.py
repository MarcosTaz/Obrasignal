import sqlite3
from decimal import Decimal

import pytest

from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import AssistedCaseState, recovery_case_to_payload
from factories.capacity_commitment.synthetic_cases import case
from factories.capacity_commitment.web import create_app


def make_state(tenant_id: str, case_id: str, *, actual_units=Decimal("80000")) -> AssistedCaseState:
    return AssistedCaseState(
        tenant_id=tenant_id,
        company_id=f"company-{tenant_id}",
        customer_id="oem-1",
        program_id="program-1",
        recovery_case=case(case_id, actual_units=actual_units),
        evidence_refs=("contract:1", "actuals:1"),
        contract_id="lta-2026-01",
        forecast_units=Decimal("110000"),
        deadline="2099-09-30",
    )


def web_payload(case_id: str, *, actual_units=Decimal("80000")) -> dict:
    return {
        "company_id": "supplier-1",
        "customer_id": "oem-1",
        "program_id": "program-1",
        "contract_id": "lta-2026-01",
        "forecast_units": "110000",
        "recovery_case": recovery_case_to_payload(case(case_id, actual_units=actual_units)),
        "evidence_refs": ["contract:1", "actuals:1"],
        "missing_evidence": [],
        "deadline": "2099-09-30",
    }


def headers(tenant="tenant-a", intent=None):
    result = {"X-Test-Tenant": tenant}
    if intent is not None:
        result["X-Capacity-Intent"] = intent
    return result


def test_revision_preserves_parent_snapshot_and_builds_ordered_lineage(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    root = make_state("tenant-a", "case-v1", actual_units=Decimal("80000"))
    revised = make_state("tenant-a", "case-v2", actual_units=Decimal("70000"))
    repo.save(root)

    assert repo.create_revision(revised, parent_case_id="case-v1") is True
    assert repo.load(tenant_id="tenant-a", case_id="case-v1") == root
    assert repo.load(tenant_id="tenant-a", case_id="case-v2") == revised
    assert repo.revision_lineage(tenant_id="tenant-a", case_id="case-v2") == ["case-v1", "case-v2"]
    assert repo.list_revision_children(tenant_id="tenant-a", parent_case_id="case-v1") == ["case-v2"]


def test_revision_chain_can_extend_without_overwriting_earlier_evidence(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    v1 = make_state("tenant-a", "case-v1", actual_units=Decimal("80000"))
    v2 = make_state("tenant-a", "case-v2", actual_units=Decimal("70000"))
    v3 = make_state("tenant-a", "case-v3", actual_units=Decimal("60000"))
    repo.save(v1)
    repo.create_revision(v2, parent_case_id="case-v1")
    repo.create_revision(v3, parent_case_id="case-v2")

    assert repo.revision_lineage(tenant_id="tenant-a", case_id="case-v3") == [
        "case-v1",
        "case-v2",
        "case-v3",
    ]
    assert repo.load(tenant_id="tenant-a", case_id="case-v1") == v1
    assert repo.load(tenant_id="tenant-a", case_id="case-v2") == v2


def test_revision_exact_retry_is_idempotent_but_parent_or_source_drift_conflicts(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    repo.save(make_state("tenant-a", "root-a"))
    repo.save(make_state("tenant-a", "root-b"))
    child = make_state("tenant-a", "child", actual_units=Decimal("70000"))

    assert repo.create_revision(child, parent_case_id="root-a") is True
    assert repo.create_revision(child, parent_case_id="root-a") is False

    with pytest.raises(FileExistsError, match="different source state or parent"):
        repo.create_revision(child, parent_case_id="root-b")

    changed_child = make_state("tenant-a", "child", actual_units=Decimal("0"))
    with pytest.raises(FileExistsError, match="different source state or parent"):
        repo.create_revision(changed_child, parent_case_id="root-a")


def test_revision_requires_new_child_identity(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    root = make_state("tenant-a", "same-id")
    repo.save(root)

    with pytest.raises(ValueError, match="must differ"):
        repo.create_revision(root, parent_case_id="same-id")


def test_revision_parent_is_tenant_scoped_and_cross_tenant_attempt_persists_nothing(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    repo.save(make_state("tenant-a", "root"))
    foreign_child = make_state("tenant-b", "child")

    with pytest.raises(KeyError, match="not found"):
        repo.create_revision(foreign_child, parent_case_id="root")

    assert repo.list_case_ids(tenant_id="tenant-b") == []


def test_revision_lineage_fails_closed_on_corrupted_cycle(tmp_path):
    db_path = tmp_path / "capacity.db"
    repo = CapacityRepository(str(db_path))
    repo.save(make_state("tenant-a", "v1"))
    repo.create_revision(make_state("tenant-a", "v2"), parent_case_id="v1")
    repo.create_revision(make_state("tenant-a", "v3"), parent_case_id="v2")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE capacity_commitment_case_revisions SET parent_case_id='v3' "
            "WHERE tenant_id='tenant-a' AND child_case_id='v2'"
        )

    with pytest.raises(RuntimeError, match="lineage cycle"):
        repo.revision_lineage(tenant_id="tenant-a", case_id="v3")


def test_revision_backup_restore_preserves_lineage_and_removes_post_backup_children(tmp_path):
    live_path = tmp_path / "live.db"
    backup_path = tmp_path / "backup.db"
    repo = CapacityRepository(str(live_path))
    repo.save(make_state("tenant-a", "v1"))
    repo.create_revision(make_state("tenant-a", "v2"), parent_case_id="v1")
    repo.backup_to(str(backup_path))
    repo.create_revision(make_state("tenant-a", "v3"), parent_case_id="v2")

    repo.restore_from(str(backup_path))

    assert repo.revision_lineage(tenant_id="tenant-a", case_id="v2") == ["v1", "v2"]
    assert repo.list_revision_children(tenant_id="tenant-a", parent_case_id="v2") == []
    with pytest.raises(KeyError):
        repo.load(tenant_id="tenant-a", case_id="v3")


def test_restore_rejects_missing_parent_lineage_before_live_mutation(tmp_path):
    live_path = tmp_path / "live.db"
    backup_path = tmp_path / "bad.db"
    live = CapacityRepository(str(live_path))
    original = make_state("tenant-a", "live-root")
    live.save(original)

    bad = CapacityRepository(str(backup_path))
    bad.save(make_state("tenant-a", "v1"))
    bad.create_revision(make_state("tenant-a", "v2"), parent_case_id="v1")
    with sqlite3.connect(backup_path) as conn:
        conn.execute(
            "UPDATE capacity_commitment_case_revisions SET parent_case_id='missing-parent' "
            "WHERE child_case_id='v2'"
        )

    with pytest.raises(ValueError, match="missing or cross-tenant"):
        live.restore_from(str(backup_path))

    assert live.load(tenant_id="tenant-a", case_id="live-root") == original


def test_web_revision_endpoint_preserves_parent_and_exposes_lineage(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repo, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    client = app.test_client()

    root = client.post(
        "/api/capacity/cases",
        headers=headers(intent="create-case"),
        json=web_payload("web-v1", actual_units=Decimal("80000")),
    )
    assert root.status_code == 201
    assert root.get_json()["revision_lineage"] == ["web-v1"]

    revised = client.post(
        "/api/capacity/cases/web-v1/revisions",
        headers=headers(intent="create-revision"),
        json=web_payload("web-v2", actual_units=Decimal("70000")),
    )
    assert revised.status_code == 201
    assert revised.get_json()["revision_lineage"] == ["web-v1", "web-v2"]

    original = client.get("/api/capacity/cases/web-v1", headers=headers())
    assert original.status_code == 200
    assert original.get_json()["case"]["actual_units"] == "80000"
    assert original.get_json()["revision_lineage"] == ["web-v1"]

    lineage = client.get("/api/capacity/cases/web-v2/lineage", headers=headers())
    assert lineage.status_code == 200
    assert lineage.get_json() == {"children": [], "count": 2, "items": ["web-v1", "web-v2"]}


def test_web_revision_requires_explicit_revision_intent(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repo, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    client = app.test_client()
    client.post(
        "/api/capacity/cases",
        headers=headers(intent="create-case"),
        json=web_payload("root"),
    )

    response = client.post(
        "/api/capacity/cases/root/revisions",
        headers=headers(),
        json=web_payload("child"),
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "revision_intent_required"
    assert repo.list_case_ids(tenant_id="tenant-a") == ["root"]


def test_web_revision_cannot_attach_to_other_tenant_parent(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repo, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    client = app.test_client()
    client.post(
        "/api/capacity/cases",
        headers=headers("tenant-a", intent="create-case"),
        json=web_payload("root"),
    )

    response = client.post(
        "/api/capacity/cases/root/revisions",
        headers=headers("tenant-b", intent="create-revision"),
        json=web_payload("foreign-child"),
    )

    assert response.status_code == 404
    assert repo.list_case_ids(tenant_id="tenant-b") == []


def test_web_lineage_endpoint_is_tenant_isolated(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_app(repo, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    client = app.test_client()
    client.post(
        "/api/capacity/cases",
        headers=headers("tenant-a", intent="create-case"),
        json=web_payload("root"),
    )

    response = client.get(
        "/api/capacity/cases/root/lineage",
        headers=headers("tenant-b"),
    )
    assert response.status_code == 404
