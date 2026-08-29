import sqlite3

import app
import france_runtime
from signal_store import get_signal_record, persist_signal_records
from source_registry import SOURCES, production_gate_reasons


def _contract(value="100000"):
    return {
        "source": "FR_DECP",
        "signal_type": "CONTRACT",
        "external_id": "FR-1",
        "title": "Travaux de rénovation",
        "country": "FRA",
        "value": value,
        "currency": "EUR",
        "publication_date": "2026-08-24",
        "source_updated_at": "2026-08-24T00:00:00Z",
        "taxonomy": "CPV",
        "category_code": "45400000-1",
        "url": "https://www.data.economie.gouv.fr/",
    }


def test_registry_contract_is_explicit_and_green():
    meta = SOURCES["FR_DECP"]
    assert meta["country"] == "FRA"
    assert meta["signal_types"] == ("CONTRACT",)
    assert meta["legal_reuse"] == "GREEN"
    assert meta["machine_access"] == "VERIFIED"
    assert meta["status"] == "ready"
    assert production_gate_reasons("FR_DECP") == ()


def test_runtime_installs_once_without_choosing_activation_policy(monkeypatch):
    calls = []

    def fake_install(app_module, **kwargs):
        calls.append((app_module, kwargs))
        return "wrapped"

    monkeypatch.setattr(france_runtime, "install_incremental_source", fake_install)
    enabled = lambda source: source == "FR_DECP"
    blocked = lambda source: None

    assert france_runtime.install_france_decp_runtime(
        app, source_enabled=enabled, record_blocked=blocked
    ) == "wrapped"
    assert calls[0][0] is app
    assert calls[0][1]["source"] == "FR_DECP"
    assert calls[0][1]["source_enabled"] is enabled
    assert calls[0][1]["record_blocked"] is blocked


def test_runtime_rejects_missing_gate_callbacks():
    try:
        france_runtime.install_france_decp_runtime(
            app, source_enabled=None, record_blocked=lambda source: None
        )
    except TypeError as exc:
        assert "explicit gate" in str(exc)
    else:
        raise AssertionError("missing activation gate must fail closed")


def test_contract_persistence_is_idempotent_and_update_safe():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    persist_signal_records(conn, [_contract("100000")], expected_source="FR_DECP")
    persist_signal_records(conn, [_contract("125000")], expected_source="FR_DECP")

    count = conn.execute(
        "SELECT COUNT(*) FROM signal_records WHERE source='FR_DECP' AND signal_type='CONTRACT'"
    ).fetchone()[0]
    row = get_signal_record(conn, "FR_DECP", "FR-1", "CONTRACT")
    assert count == 1
    assert row["value"] == "125000"
