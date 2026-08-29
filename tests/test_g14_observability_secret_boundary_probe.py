from datetime import datetime, timezone
import sqlite3

from source_health import ensure_source_health, record_source_result, source_health_contract


def test_g14_public_source_health_contract_never_exposes_secret_bearing_error_text():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    secret = "super-secret-provider-token-123"
    record_source_result(
        conn,
        "TED",
        success=False,
        duration_ms=321,
        error=f"401 upstream rejected Authorization Bearer {secret}",
        observed_at=datetime(2026, 8, 29, 19, 0, tzinfo=timezone.utc),
    )

    contract = source_health_contract(
        conn,
        sources=["TED"],
        now=datetime(2026, 8, 29, 19, 1, tzinfo=timezone.utc),
    )
    item = contract["items"][0]

    # Public/customer-facing observability may expose that a source failed and a
    # bounded diagnostic class, but never raw upstream exception text that can
    # carry bearer tokens, query credentials, signed URLs, or provider payloads.
    serialized = repr(contract)
    assert secret not in serialized
    assert "Authorization Bearer" not in serialized
    assert item["health"] == "degraded"
    assert item["consecutive_failures"] == 1
    assert item["last_error"] in (None, "upstream_failure")
    conn.close()
