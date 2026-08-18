import sqlite3


def test_account_registry_creates_and_lists_active_accounts():
    from account_registry import ensure_account, list_active_accounts

    conn = sqlite3.connect(":memory:")
    ensure_account(conn, "empresa-a", plan="pilot")
    ensure_account(conn, "empresa-b", status="inactive", plan="pro")

    assert list_active_accounts(conn) == ["empresa-a"]
    conn.close()
