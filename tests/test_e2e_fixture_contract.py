import concurrent.futures
import os
import sqlite3

import api
import e2e_fixture_api
from auth_context import RequestIdentity
from e2e_fixture_api import install


install(api.APP)


def _authenticated_identity():
    account_id = os.environ["OBRASIGNAL_ACCOUNT_ID"]
    return RequestIdentity(
        account_id=account_id,
        authenticated=True,
        subject=account_id,
        claims={"sub": account_id},
    )


def _configure(monkeypatch, tmp_path, account_id="tenant-a"):
    primary_db = tmp_path / "primary.db"
    fixture_db = tmp_path / "fixtures.db"
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", account_id)
    monkeypatch.setenv("OBRASIGNAL_DB", str(primary_db))
    monkeypatch.setenv("OBRASIGNAL_TEST_FIXTURES_ENABLED", "1")
    monkeypatch.setenv("OBRASIGNAL_TEST_FIXTURE_DB", str(fixture_db))
    monkeypatch.setattr(e2e_fixture_api, "configured_identity", _authenticated_identity)
    return primary_db, fixture_db


def test_fixture_contract_is_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("OBRASIGNAL_TEST_FIXTURES_ENABLED", raising=False)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "tenant-a")
    fixture_db = tmp_path / "disabled-fixtures.db"
    monkeypatch.setenv("OBRASIGNAL_TEST_FIXTURE_DB", str(fixture_db))

    response = api.APP.test_client().post(
        "/api/v1/test-fixtures/opportunity", json={"run_id": "run-disabled"}
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}
    assert not fixture_db.exists()


def test_fixture_store_must_be_separate_from_primary_database(monkeypatch, tmp_path):
    database = tmp_path / "same.db"
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "tenant-a")
    monkeypatch.setenv("OBRASIGNAL_DB", str(database))
    monkeypatch.setenv("OBRASIGNAL_TEST_FIXTURES_ENABLED", "true")
    monkeypatch.setenv("OBRASIGNAL_TEST_FIXTURE_DB", str(database))

    response = api.APP.test_client().post(
        "/api/v1/test-fixtures/opportunity", json={"run_id": "run-same-db"}
    )

    assert response.status_code == 503
    assert response.get_json() == {"error": "fixture_contract_unavailable"}
    assert not database.exists()


def test_public_fixture_startup_seam_is_idempotent_and_never_touches_primary(monkeypatch, tmp_path):
    primary_db, fixture_db = _configure(monkeypatch, tmp_path)

    first = e2e_fixture_api.initialize_fixture_store()
    second = e2e_fixture_api.initialize_fixture_store()

    assert first == fixture_db.resolve()
    assert second == first
    assert e2e_fixture_api.fixture_store_path() == first
    assert fixture_db.exists()
    assert not primary_db.exists()
    conn = sqlite3.connect(str(fixture_db))
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "e2e_opportunity_fixtures" in tables
        assert "opportunity_workflow" in tables
    finally:
        conn.close()


def test_concurrent_create_is_idempotent_after_owner_schema_init(monkeypatch, tmp_path):
    _, fixture_db = _configure(monkeypatch, tmp_path)
    e2e_fixture_api.initialize_fixture_store()

    def create_once():
        conn = e2e_fixture_api._connect()
        try:
            row, created = e2e_fixture_api._create_fixture(conn, "tenant-a", "concurrent-run")
            return row["fixture_id"], created
        finally:
            conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: create_once(), range(24)))

    fixture_ids = {fixture_id for fixture_id, _ in results}
    assert len(fixture_ids) == 1
    assert sum(1 for _, created in results if created) == 1
    conn = sqlite3.connect(str(fixture_db))
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM e2e_opportunity_fixtures WHERE account_id=? AND run_id=?",
            ("tenant-a", "concurrent-run"),
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_fixture_contract_requires_authenticated_identity(monkeypatch, tmp_path):
    _, fixture_db = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        e2e_fixture_api,
        "configured_identity",
        lambda: RequestIdentity(account_id="tenant-a", authenticated=False),
    )

    response = api.APP.test_client().post(
        "/api/v1/test-fixtures/opportunity", json={"run_id": "run-unauthenticated"}
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication_required"}
    assert not fixture_db.exists()


def test_fixture_rejects_client_supplied_tenant_identity(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)

    response = api.APP.test_client().post(
        "/api/v1/test-fixtures/opportunity",
        json={"run_id": "run-tenant-field", "account_id": "tenant-b"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_fixture_request"
    assert response.get_json()["unexpected_fields"] == ["account_id"]


def test_authenticated_fixture_round_trip_restore_cleanup_and_tenant_isolation(monkeypatch, tmp_path):
    primary_db, fixture_db = _configure(monkeypatch, tmp_path, account_id="tenant-a")
    client = api.APP.test_client()
    run_id = "issue-277-run"

    created = client.post("/api/v1/test-fixtures/opportunity", json={"run_id": run_id})
    assert created.status_code == 201
    created_body = created.get_json()
    fixture_id = created_body["fixture_id"]
    assert fixture_id.startswith("e2e_")
    assert created_body["account_id"] == "tenant-a"
    assert created_body["authenticated"] is True
    assert created_body["created"] is True
    assert created_body["opportunity"]["test_fixture"] is True
    assert created_body["opportunity"]["market"] == "TEST"
    assert created_body["opportunity"]["workflow"]["status"] == "NEW"

    repeated = client.post("/api/v1/test-fixtures/opportunity", json={"run_id": run_id})
    assert repeated.status_code == 200
    assert repeated.get_json()["created"] is False
    assert repeated.get_json()["fixture_id"] == fixture_id

    detail = client.get(f"/api/v1/opportunities/{fixture_id}")
    workflow = client.get(f"/api/v1/opportunities/{fixture_id}/workflow")
    assert detail.status_code == 200
    assert detail.get_json()["id"] == fixture_id
    assert detail.get_json()["synthetic"] is True
    assert workflow.status_code == 200
    assert workflow.get_json()["account_id"] == "tenant-a"
    baseline = workflow.get_json()["workflow"]
    assert baseline["status"] == "NEW"
    assert baseline["note"] is None

    written = client.post(
        f"/api/v1/opportunities/{fixture_id}/workflow",
        json={"status": "PREPARING", "note": "__fixture_roundtrip__"},
    )
    assert written.status_code == 200
    readback = client.get(f"/api/v1/opportunities/{fixture_id}/workflow").get_json()["workflow"]
    assert readback["status"] == "PREPARING"
    assert readback["note"] == "__fixture_roundtrip__"

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "tenant-b")
    assert client.get(f"/api/v1/opportunities/{fixture_id}").status_code == 404
    assert client.get(f"/api/v1/opportunities/{fixture_id}/workflow").status_code == 404
    assert client.post(
        f"/api/v1/opportunities/{fixture_id}/workflow",
        json={"status": "WON", "note": "must-not-cross-tenant"},
    ).status_code == 404
    foreign_cleanup = client.post(
        "/api/v1/test-fixtures/opportunity/cleanup", json={"run_id": run_id}
    )
    assert foreign_cleanup.status_code == 200
    assert foreign_cleanup.get_json()["cleaned"] is False

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "tenant-a")
    still_owned = client.get(f"/api/v1/opportunities/{fixture_id}/workflow").get_json()["workflow"]
    assert still_owned["status"] == "PREPARING"
    assert still_owned["note"] == "__fixture_roundtrip__"

    restored = client.post(
        f"/api/v1/opportunities/{fixture_id}/workflow",
        json={"status": baseline["status"], "note": baseline["note"]},
    )
    assert restored.status_code == 200
    restored_readback = client.get(
        f"/api/v1/opportunities/{fixture_id}/workflow"
    ).get_json()["workflow"]
    assert restored_readback["status"] == baseline["status"]
    assert restored_readback["note"] == baseline["note"]

    cleaned = client.post(
        "/api/v1/test-fixtures/opportunity/cleanup", json={"run_id": run_id}
    )
    assert cleaned.status_code == 200
    assert cleaned.get_json()["cleaned"] is True
    assert client.get(f"/api/v1/opportunities/{fixture_id}").status_code == 404

    cleaned_again = client.post(
        "/api/v1/test-fixtures/opportunity/cleanup", json={"run_id": run_id}
    )
    assert cleaned_again.status_code == 200
    assert cleaned_again.get_json()["already_absent"] is True

    assert fixture_db.exists()
    assert not primary_db.exists(), "fixture contract must never touch the primary data store"
    conn = sqlite3.connect(str(fixture_db))
    try:
        fixture_count = conn.execute("SELECT COUNT(*) FROM e2e_opportunity_fixtures").fetchone()[0]
        workflow_count = conn.execute("SELECT COUNT(*) FROM opportunity_workflow").fetchone()[0]
    finally:
        conn.close()
    assert fixture_count == 0
    assert workflow_count == 0


def test_failure_path_can_be_cleaned_without_partial_workflow_state(monkeypatch, tmp_path):
    _, fixture_db = _configure(monkeypatch, tmp_path, account_id="tenant-a")
    client = api.APP.test_client()
    run_id = "issue-277-failure"
    fixture_id = client.post(
        "/api/v1/test-fixtures/opportunity", json={"run_id": run_id}
    ).get_json()["fixture_id"]

    failed = client.post(
        f"/api/v1/opportunities/{fixture_id}/workflow",
        json={"status": "NOT_A_REAL_STATUS", "note": "must-not-persist"},
    )
    assert failed.status_code == 400
    current = client.get(f"/api/v1/opportunities/{fixture_id}/workflow").get_json()["workflow"]
    assert current["status"] == "NEW"
    assert current["note"] is None

    cleanup = client.post(
        "/api/v1/test-fixtures/opportunity/cleanup", json={"run_id": run_id}
    )
    assert cleanup.status_code == 200
    assert cleanup.get_json()["cleaned"] is True

    conn = sqlite3.connect(str(fixture_db))
    try:
        assert conn.execute("SELECT COUNT(*) FROM e2e_opportunity_fixtures").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM opportunity_workflow").fetchone()[0] == 0
    finally:
        conn.close()
