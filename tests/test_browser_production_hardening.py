import sqlite3
from pathlib import Path
from types import SimpleNamespace

import account_privacy as privacy
from app import APP
from traffic_analytics import (
    PUBLISHED_FALLBACK_ORIGIN,
    _origin_allowed,
    ensure_traffic_schema,
)

ROOT = Path(__file__).resolve().parents[1]


class _NoCloseConnection:
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        return None


def test_published_fallback_is_allowed_even_if_render_env_has_not_synced(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_WEB_ORIGIN", "https://obrasignal.com")
    monkeypatch.delenv("OBRASIGNAL_CORS_FALLBACK_ORIGIN", raising=False)

    with APP.test_request_context(
        "/api/v1/analytics/event",
        headers={"Origin": PUBLISHED_FALLBACK_ORIGIN},
    ):
        assert _origin_allowed() is True


def test_traffic_schema_hot_path_is_read_only_after_startup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_traffic_schema(conn)

    statements = []
    conn.set_trace_callback(statements.append)
    ensure_traffic_schema(conn)
    conn.set_trace_callback(None)

    normalized = [statement.lstrip().upper() for statement in statements]
    assert not any(
        statement.startswith(("CREATE ", "ALTER ", "DROP "))
        for statement in normalized
    )


def test_existing_privacy_account_never_enters_bootstrap_writer(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE accounts(
            account_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'active',
            plan TEXT NOT NULL DEFAULT 'evaluation',
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO accounts(account_id,status,plan,created_at) VALUES(?,?,?,?)",
        ("acct-existing", "active", "evaluation", "2026-09-01T00:00:00+00:00"),
    )
    conn.commit()

    monkeypatch.setattr(privacy, "_db", lambda: _NoCloseConnection(conn))
    monkeypatch.setattr(
        privacy,
        "configured_identity",
        lambda: SimpleNamespace(account_id="acct-existing"),
    )

    def forbidden_bootstrap(*args, **kwargs):
        raise AssertionError("existing privacy GET must not invoke account bootstrap")

    monkeypatch.setattr(privacy, "ensure_account", forbidden_bootstrap)
    identity, failure = privacy._identity_or_response()

    assert failure is None
    assert identity.account_id == "acct-existing"


def test_api_cors_source_keeps_exact_published_fallback_without_wildcard():
    source = (ROOT / "cors_app.py").read_text(encoding="utf-8")
    assert 'PUBLISHED_FALLBACK_ORIGIN = "https://marcostaz.github.io"' in source
    assert "published_fallback = _normalized_origin(PUBLISHED_FALLBACK_ORIGIN)" in source
    assert 'PUBLISHED_FALLBACK_ORIGIN = "*"' not in source
