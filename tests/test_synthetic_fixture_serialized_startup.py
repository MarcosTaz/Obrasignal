import concurrent.futures
import sqlite3

import e2e_fixture_api
from fixture_storage_contract import verify_fixture_store
from storage_migration_lock import run_serialized_schema_init


def test_actual_fixture_owner_initialization_is_serialized_on_concurrent_first_start(monkeypatch, tmp_path):
    primary_db = tmp_path / "primary.db"
    fixture_db = tmp_path / "fixtures.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(primary_db))
    monkeypatch.setenv("OBRASIGNAL_TEST_FIXTURES_ENABLED", "1")
    monkeypatch.setenv("OBRASIGNAL_TEST_FIXTURE_DB", str(fixture_db))

    def initialize_once():
        run_serialized_schema_init(e2e_fixture_api.initialize_fixture_store, fixture_db)
        return e2e_fixture_api.fixture_store_path()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: initialize_once(), range(24)))

    assert set(results) == {fixture_db.resolve()}
    assert fixture_db.exists()
    assert not primary_db.exists(), "synthetic fixture startup must never initialize primary customer storage"

    conn = sqlite3.connect(fixture_db)
    try:
        verify_fixture_store(conn)
    finally:
        conn.close()
