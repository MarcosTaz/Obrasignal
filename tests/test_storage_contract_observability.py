import sqlite3

from storage_contract import contract_fingerprint
from storage_recovery import create_backup_artifact, inspect_database, verify_backup_artifact


def test_expected_contract_fingerprint_is_deterministic_and_not_db_state(tmp_path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE arbitrary_state(id INTEGER PRIMARY KEY, body TEXT)")
    conn.commit()
    conn.close()

    first = contract_fingerprint(include_runtime=True)
    second = contract_fingerprint(include_runtime=True)
    assert first == second
    assert len(first) == 64

    health = inspect_database(db_path)
    assert health["expected_contract_fingerprint"] == first
    # The expected contract fingerprint is repository metadata. It is distinct
    # from the actual SQLite schema fingerprint and does not claim this arbitrary
    # synthetic DB satisfies the ObraSignal storage contract.
    assert health["schema_fingerprint"] != health["expected_contract_fingerprint"]


def test_backup_manifest_carries_contract_fingerprint_without_requiring_db_ledger(tmp_path):
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE state(id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    result = create_backup_artifact(db_path, tmp_path / "backup")
    assert result["expected_contract_fingerprint"] == contract_fingerprint(include_runtime=True)
    verified = verify_backup_artifact(result["artifact"], result["manifest"])
    assert verified["expected_contract_fingerprint"] == result["expected_contract_fingerprint"]

    # No migration-history table is created as a side effect of inspection or
    # backup: owner migrations remain the only schema writers.
    conn = sqlite3.connect(db_path)
    try:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert names == {"state"}
    finally:
        conn.close()
