import sqlite3

import pytest

from storage_contract import STARTUP_CONTRACTS, verify_schema
from storage_migration_lock import run_serialized_schema_init


def test_startup_interruption_after_prior_owner_commit_converges_on_restart(monkeypatch, tmp_path):
    """A later startup failure must not make earlier committed schema look complete.

    Current startup is additive but not globally atomic because owner ensure
    functions may commit internally.  This test deliberately stops after the
    account owner has run, then restarts the same initializer and requires the
    complete registered startup schema to converge without losing the already
    durable account row.
    """
    import app
    import company_profile

    path = tmp_path / "partial-startup.db"
    monkeypatch.setattr(app, "DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))

    original = company_profile.ensure_profile_table
    injected = {"raised": False}

    def interrupt_once(conn):
        if not injected["raised"]:
            injected["raised"] = True
            raise RuntimeError("controlled startup interruption")
        return original(conn)

    monkeypatch.setattr(company_profile, "ensure_profile_table", interrupt_once)

    with pytest.raises(RuntimeError, match="controlled startup interruption"):
        run_serialized_schema_init(app.init_db, path)

    # The earlier account owner committed before the controlled interruption.
    conn = sqlite3.connect(path)
    try:
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts'"
        ).fetchone() == (1,)
    finally:
        conn.close()

    # A service restart/rerun must converge from that partial durable state.
    run_serialized_schema_init(app.init_db, path)
    conn = app.db()
    try:
        verify_schema(conn, STARTUP_CONTRACTS)
    finally:
        conn.close()


def test_service_reopen_is_not_data_state_verified_without_schema_verification(monkeypatch, tmp_path):
    """Opening SQLite successfully is weaker than verifying durable state."""
    import app

    path = tmp_path / "incomplete.db"
    monkeypatch.setattr(app, "DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))

    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE tenders(id INTEGER PRIMARY KEY, source TEXT, external_id TEXT)")
    conn.commit()
    conn.close()

    # Dependency/service is available: the database can be opened.
    reopened = app.db()
    reopened.close()

    # But incomplete durable state must not be called recovered.
    verify_conn = app.db()
    try:
        with pytest.raises(Exception):
            verify_schema(verify_conn, STARTUP_CONTRACTS)
    finally:
        verify_conn.close()
