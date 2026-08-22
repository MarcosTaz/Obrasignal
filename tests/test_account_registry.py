import sqlite3


def test_account_registry_creates_and_lists_active_accounts():
    from account_registry import ensure_account, list_active_accounts

    conn = sqlite3.connect(":memory:")
    ensure_account(conn, "empresa-a", plan="pilot")
    ensure_account(conn, "empresa-b", status="inactive", plan="pro")

    assert list_active_accounts(conn) == ["empresa-a"]
    conn.close()


def test_existing_account_initialization_is_read_only_during_sync_writer(tmp_path):
    from account_registry import ensure_account

    db_path = tmp_path / "accounts.db"
    locker = sqlite3.connect(db_path)
    ensure_account(locker, "empresa-a")
    locker.execute("BEGIN IMMEDIATE")

    reader = sqlite3.connect(db_path, timeout=0.001)
    reader.execute("PRAGMA busy_timeout=1")
    ensure_account(reader, "empresa-a", status="inactive", plan="pro")
    row = reader.execute(
        "SELECT status, plan FROM accounts WHERE account_id='empresa-a'"
    ).fetchone()

    assert row == ("active", "pilot")
    reader.close()
    locker.rollback()
    locker.close()
