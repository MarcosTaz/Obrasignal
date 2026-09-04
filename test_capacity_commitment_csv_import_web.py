import io

from factories.capacity_commitment.application import create_completion_app
from factories.capacity_commitment.evidence import EvidenceRepository, ReviewState
from factories.capacity_commitment.repository import CapacityRepository


CSV = (
    "fact_id,fact_type,raw_value,normalized_value,scope_ref,page_ref,clause_ref\n"
    "actual-a,ACTUAL_UNITS,100,100,shipment-a,row:2,\n"
).encode("utf-8")


def headers(tenant="tenant-a", intent=None):
    out = {"X-Test-Tenant": tenant}
    if intent:
        out["X-Capacity-Intent"] = intent
    return out


def make_client(tmp_path):
    repo = CapacityRepository(str(tmp_path / "capacity.db"))
    app = create_completion_app(repo, lambda req: req.headers.get("X-Test-Tenant"))
    app.config.update(TESTING=True)
    return repo, app.test_client()


def upload_data(*, commit=False):
    data = {
        "evidence_id": "csv-1",
        "file": (io.BytesIO(CSV), "actuals.csv"),
    }
    if commit:
        data.update(
            {
                "kind": "ACTUALS",
                "display_name": "actuals.csv",
                "external_ref": "data-room:actuals.csv",
                "captured_at": "2026-09-04T14:00:00Z",
            }
        )
    return data


def test_csv_preview_returns_unreviewed_rows_without_persistence(tmp_path):
    repo, client = make_client(tmp_path)
    response = client.post(
        "/api/capacity/evidence/import/csv/preview",
        headers=headers(),
        data=upload_data(),
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["row_count"] == 1
    assert body["facts"][0]["review_state"] == "UNREVIEWED"
    assert body["facts"][0]["scope_ref"] == "shipment-a"
    assert EvidenceRepository(repo.db_path).list_sources(tenant_id="tenant-a") == []


def test_csv_commit_requires_intent_and_persists_only_current_tenant(tmp_path):
    repo, client = make_client(tmp_path)
    denied = client.post(
        "/api/capacity/evidence/import/csv",
        headers=headers(),
        data=upload_data(commit=True),
        content_type="multipart/form-data",
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/capacity/evidence/import/csv",
        headers=headers(intent="import-csv-evidence"),
        data=upload_data(commit=True),
        content_type="multipart/form-data",
    )
    assert created.status_code == 201
    body = created.get_json()
    assert body["facts_inserted"] == 1
    assert body["review_state"] == "UNREVIEWED"
    assert body["raw_content_retained"] is False
    assert body["source_external_ref"] == "data-room:actuals.csv"

    evidence = EvidenceRepository(repo.db_path)
    assert len(evidence.list_sources(tenant_id="tenant-a")) == 1
    assert len(evidence.list_facts(tenant_id="tenant-a")) == 1
    assert evidence.list_sources(tenant_id="tenant-b") == []
    assert evidence.list_facts(tenant_id="tenant-b") == []


def test_csv_reimport_after_human_confirmation_cannot_reset_review(tmp_path):
    repo, client = make_client(tmp_path)
    first = client.post(
        "/api/capacity/evidence/import/csv",
        headers=headers(intent="import-csv-evidence"),
        data=upload_data(commit=True),
        content_type="multipart/form-data",
    )
    assert first.status_code == 201
    evidence = EvidenceRepository(repo.db_path)
    evidence.review_fact(tenant_id="tenant-a", fact_id="actual-a", decision=ReviewState.CONFIRMED)

    second = client.post(
        "/api/capacity/evidence/import/csv",
        headers=headers(intent="import-csv-evidence"),
        data=upload_data(commit=True),
        content_type="multipart/form-data",
    )
    assert second.status_code == 409
    assert second.get_json()["error"] == "csv_import_conflict"
    assert evidence.load_fact(tenant_id="tenant-a", fact_id="actual-a").review_state is ReviewState.CONFIRMED


def test_csv_preview_rejects_wrong_header_without_persistence(tmp_path):
    repo, client = make_client(tmp_path)
    bad = b"fact_id,fact_type,raw_value\na,ACTUAL_UNITS,1\n"
    response = client.post(
        "/api/capacity/evidence/import/csv/preview",
        headers=headers(),
        data={"evidence_id": "bad", "file": (io.BytesIO(bad), "bad.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "header must exactly match" in response.get_json()["detail"]
    assert EvidenceRepository(repo.db_path).list_sources(tenant_id="tenant-a") == []
