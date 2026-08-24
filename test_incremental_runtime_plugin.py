from incremental_runtime_plugin import build_incremental_source_wrapper, install_incremental_source
import incremental_runtime_plugin as runtime_plugin


class FakeConn:
    def close(self):
        pass


class FakeAppModule:
    def __init__(self, fetch_base):
        self.fetch_base = fetch_base
        self.db = lambda: FakeConn()


def test_blocked_source_never_fetches_and_preserves_existing_rows(monkeypatch):
    events = []
    fetch_calls = []
    wrapped = build_incremental_source_wrapper(
        lambda: [{"source": "BASE", "external_id": "base-1"}],
        source="LV_IUB",
        fetch_incremental=lambda **kwargs: fetch_calls.append(kwargs),
        source_enabled=lambda source: False,
        record_blocked=lambda source: events.append(("blocked", source)),
        db=lambda: FakeConn(),
    )
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    rows = wrapped()

    assert rows == [{"source": "BASE", "external_id": "base-1"}]
    assert fetch_calls == []
    assert events == [("blocked", "LV_IUB")]


def test_enabled_source_reads_cursor_stages_it_and_records_health(monkeypatch):
    staged = []
    health = []
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old-cursor")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(
        runtime_plugin,
        "record_source_result",
        lambda conn, source, **kwargs: health.append((source, kwargs)),
    )
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def fetch_incremental(*, watermark=None):
        assert watermark == "old-cursor"
        return [{"source": "LV_IUB", "external_id": "lv-1"}], "new-cursor"

    wrapped = build_incremental_source_wrapper(
        lambda: [{"source": "BASE", "external_id": "base-1"}],
        source="LV_IUB",
        fetch_incremental=fetch_incremental,
        source_enabled=lambda source: True,
        record_blocked=lambda source: (_ for _ in ()).throw(AssertionError("should not block")),
        db=lambda: FakeConn(),
    )

    rows = wrapped()

    assert [row["external_id"] for row in rows] == ["base-1", "lv-1"]
    assert staged == [("LV_IUB", [{"source": "LV_IUB", "external_id": "lv-1"}], "new-cursor")]
    assert len(health) == 1
    assert health[0][0] == "LV_IUB"
    assert health[0][1]["success"] is True
    assert health[0][1]["found"] == 1


def test_lifecycle_only_observation_is_staged_but_never_emitted_to_legacy_tenders(monkeypatch):
    staged = []
    health = []
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old-cursor")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda source, rows, cursor: staged.append((source, rows, cursor)))
    monkeypatch.setattr(
        runtime_plugin,
        "record_source_result",
        lambda conn, source, **kwargs: health.append((source, kwargs)),
    )
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    live = {"source": "UK_PROCUREMENT", "external_id": "ocid-open", "is_actionable": True}
    tombstone = {
        "source": "UK_PROCUREMENT",
        "external_id": "ocid-closed",
        "is_actionable": False,
        "lifecycle_status": "complete",
        "_lifecycle_only": True,
    }

    wrapped = build_incremental_source_wrapper(
        lambda: [{"source": "BASE", "external_id": "base-1"}],
        source="UK_PROCUREMENT",
        fetch_incremental=lambda *, watermark=None: ([live, tombstone], "new-cursor"),
        source_enabled=lambda source: True,
        record_blocked=lambda source: None,
        db=lambda: FakeConn(),
    )

    rows = wrapped()

    assert [row["external_id"] for row in rows] == ["base-1", "ocid-open"]
    assert staged == [("UK_PROCUREMENT", [live, tombstone], "new-cursor")]
    assert health[0][1]["found"] == 2


def test_incremental_failure_is_isolated_and_cursor_is_not_staged(monkeypatch):
    staged = []
    health = []
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: "old-cursor")
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda *args: staged.append(args))
    monkeypatch.setattr(
        runtime_plugin,
        "record_source_result",
        lambda conn, source, **kwargs: health.append((source, kwargs)),
    )
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    def broken_fetch(*, watermark=None):
        raise RuntimeError("source unavailable")

    wrapped = build_incremental_source_wrapper(
        lambda: [{"source": "BASE", "external_id": "base-1"}],
        source="LV_IUB",
        fetch_incremental=broken_fetch,
        source_enabled=lambda source: True,
        record_blocked=lambda source: None,
        db=lambda: FakeConn(),
    )

    rows = wrapped()

    assert rows == [{"source": "BASE", "external_id": "base-1"}]
    assert staged == []
    assert len(health) == 1
    assert health[0][1]["success"] is False
    assert "source unavailable" in str(health[0][1]["error"])


def test_install_is_idempotent_and_tracks_installed_sources(monkeypatch):
    monkeypatch.setattr(runtime_plugin, "get_source_cursor", lambda conn, source: None)
    monkeypatch.setattr(runtime_plugin, "record_source_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_plugin, "stage_source_sync", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime_plugin, "dedupe_records", lambda rows: rows)

    app_module = FakeAppModule(lambda: [])
    first = install_incremental_source(
        app_module,
        source="LV_IUB",
        fetch_incremental=lambda **kwargs: ([], "cursor"),
        source_enabled=lambda source: True,
        record_blocked=lambda source: None,
    )
    second = install_incremental_source(
        app_module,
        source="LV_IUB",
        fetch_incremental=lambda **kwargs: ([], "different"),
        source_enabled=lambda source: True,
        record_blocked=lambda source: None,
    )

    assert first is second
    assert app_module.fetch_base is first
    assert first._obrasignal_incremental_sources == frozenset({"LV_IUB"})
