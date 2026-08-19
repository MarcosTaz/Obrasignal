import sqlite3
import pytest


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_workflow_defaults_and_updates_are_account_scoped():
    from opportunity_workflow import get_workflow, set_workflow

    conn = _conn()
    first = get_workflow(conn, "empresa-a", "TED", "X-1")
    assert first["status"] == "NEW"
    assert first["note"] is None

    updated = set_workflow(conn, "empresa-a", "TED", "X-1", "REVIEWING", "Verificar documentação")
    assert updated["status"] == "REVIEWING"
    assert updated["note"] == "Verificar documentação"

    other = get_workflow(conn, "empresa-b", "TED", "X-1")
    assert other["status"] == "NEW"
    assert other["note"] is None
    conn.close()


def test_workflow_rejects_unknown_status():
    from opportunity_workflow import set_workflow

    conn = _conn()
    with pytest.raises(ValueError, match="invalid workflow status"):
        set_workflow(conn, "empresa-a", "TED", "X-2", "NOT_A_STATUS")
    conn.close()


def test_workflow_supports_operational_lifecycle():
    from opportunity_workflow import set_workflow

    conn = _conn()
    for status in ("REVIEWING", "PREPARING", "SUBMITTED", "WON", "LOST"):
        result = set_workflow(conn, "empresa-a", "TED", "X-3", status)
        assert result["status"] == status
    conn.close()
