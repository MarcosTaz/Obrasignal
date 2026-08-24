import preload
from source_registry import SOURCES, production_gate_reasons
from source_runtime import discard_staged_source_syncs, staged_source_syncs


class FakeConn:
    def close(self):
        pass


def test_za_stays_blocked_while_registry_is_planned_even_if_requested(monkeypatch):
    assert SOURCES["ZA_ETENDERS"]["status"] == "planned"
    assert "runtime_not_enabled" in production_gate_reasons("ZA_ETENDERS")
    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "ZA_ETENDERS")
    assert preload._global_source_enabled("ZA_ETENDERS") is False


def test_za_fetch_stages_cursor_instead_of_committing_it(monkeypatch):
    discard_staged_source_syncs()
    monkeypatch.setattr(preload._app, "db", lambda: FakeConn())
    monkeypatch.setattr(preload, "get_source_cursor", lambda conn, source: "za-old")
    row = {"source": "ZA_ETENDERS", "external_id": "ocds-9t57fa-100"}

    def fake_fetch(*, watermark=None):
        assert watermark == "za-old"
        return [row], "za-new"

    monkeypatch.setattr(preload._south_africa_etenders, "fetch_za_tenders", fake_fetch)
    rows = preload._fetch_za_staged()

    assert rows == [row]
    staged = staged_source_syncs()
    assert len(staged) == 1
    assert staged[0].source == "ZA_ETENDERS"
    assert staged[0].cursor == "za-new"
    discard_staged_source_syncs()


def test_za_runtime_empty_increment_is_healthy_when_gate_is_open(monkeypatch):
    events = []
    monkeypatch.setenv("BASE_ACCESS_TOKEN", "configured")
    monkeypatch.setenv("OBRASIGNAL_GLOBAL_SOURCES", "ZA_ETENDERS")
    monkeypatch.setattr(preload, "production_gate_reasons", lambda source: () if source == "ZA_ETENDERS" else ("runtime_not_enabled",))
    monkeypatch.setattr(preload._app, "db", lambda: FakeConn())
    monkeypatch.setattr(preload, "_original_fetch_base", lambda: [{"source": "BASE", "external_id": "base-1"}])
    monkeypatch.setattr(preload._national_sources, "fetch_boamp", lambda: [{"source": "BOAMP", "external_id": "boamp-1"}])
    monkeypatch.setattr(preload._national_sources, "fetch_placsp", lambda: [{"source": "PLACSP", "external_id": "placsp-1"}])
    monkeypatch.setattr(preload._national_sources, "LUXEMBOURG_RSS_URL", "")
    monkeypatch.setattr(preload, "_fetch_za_staged", lambda: [])
    monkeypatch.setattr(preload, "dedupe_records", lambda rows: rows)
    monkeypatch.setattr(preload, "record_source_result", lambda conn, source, **kwargs: events.append((source, kwargs)))

    rows = preload.fetch_base_with_national_sources()

    assert len(rows) == 3
    za = [payload for source, payload in events if source == "ZA_ETENDERS"]
    assert len(za) == 1
    assert za[0]["success"] is True
    assert za[0]["found"] == 0
