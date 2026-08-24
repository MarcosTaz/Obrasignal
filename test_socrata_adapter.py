from datetime import datetime, timezone

import pytest

from socrata_adapter import SocrataCursor, SocrataProcurementAdapter, SocrataSourceConfig


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append({"url": url, "params": dict(params), "headers": dict(headers), "timeout": timeout})
        if not self.pages:
            return FakeResponse([])
        return FakeResponse(self.pages.pop(0))


def _config(**overrides):
    values = dict(
        source="TEST",
        country="TST",
        domain="example.test",
        dataset_id="abcd-1234",
        id_field="id",
        updated_field="updated_at",
        selected_fields=("id", "updated_at", "title"),
        page_size=2,
        max_pages=4,
        initial_lookback_days=2,
        overlap_minutes=60,
        base_where="kind = 'works'",
    )
    values.update(overrides)
    return SocrataSourceConfig(**values)


def test_cursor_roundtrip_and_timestamp_compatibility():
    cursor = SocrataCursor("2026-08-24T00:00:00.000", "A-1")
    assert SocrataCursor.decode(cursor.encode()) == cursor
    assert SocrataCursor.decode("2026-08-24T00:00:00.000") == SocrataCursor("2026-08-24T00:00:00.000", "")


def test_incremental_fetch_uses_keyset_pagination_not_offset():
    session = FakeSession([
        [
            {"id": "A", "updated_at": "2026-08-23T10:00:00.000", "title": "one"},
            {"id": "B", "updated_at": "2026-08-23T10:00:00.000", "title": "two"},
        ],
        [{"id": "C", "updated_at": "2026-08-23T11:00:00.000", "title": "three"}],
    ])
    adapter = SocrataProcurementAdapter(_config(), session=session)
    rows, cursor = adapter.fetch_raw_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))

    assert [row["id"] for row in rows] == ["A", "B", "C"]
    assert len(session.calls) == 2
    assert "$offset" not in session.calls[0]["params"]
    assert "$offset" not in session.calls[1]["params"]
    assert "kind = 'works'" in session.calls[0]["params"]["$where"]
    assert "updated_at >= '2026-08-22T00:00:00.000'" in session.calls[0]["params"]["$where"]
    assert "updated_at = '2026-08-23T10:00:00.000' AND id > 'B'" in session.calls[1]["params"]["$where"]
    decoded = SocrataCursor.decode(cursor)
    assert decoded == SocrataCursor("2026-08-23T11:00:00.000", "C")


def test_system_field_cursor_is_independent_from_publisher_business_fields():
    session = FakeSession([[
        {
            "external_id": "PROC-1",
            "business_updated": None,
            "source_cursor_at": "2026-08-23T09:00:00.000",
            "source_cursor_id": "row-abcd",
            "title": "one",
        }
    ]])
    adapter = SocrataProcurementAdapter(
        _config(
            page_size=10,
            id_field="external_id",
            updated_field="business_updated",
            selected_fields=("external_id", "business_updated", "title"),
            cursor_expression=":updated_at",
            cursor_alias="source_cursor_at",
            cursor_id_expression=":id",
            cursor_id_alias="source_cursor_id",
        ),
        session=session,
    )
    rows, cursor = adapter.fetch_raw_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))

    params = session.calls[0]["params"]
    assert ":updated_at AS source_cursor_at" in params["$select"]
    assert ":id AS source_cursor_id" in params["$select"]
    assert ":updated_at >= '2026-08-22T00:00:00.000'" in params["$where"]
    assert params["$order"] == ":updated_at ASC, :id ASC"
    assert rows[0]["business_updated"] is None
    assert SocrataCursor.decode(cursor) == SocrataCursor("2026-08-23T09:00:00.000", "row-abcd")


def test_system_field_keyset_uses_internal_row_id_not_external_business_id():
    session = FakeSession([
        [
            {"external_id": "PROC-Z", "source_cursor_at": "2026-08-23T10:00:00.000", "source_cursor_id": "row-001"},
            {"external_id": "PROC-A", "source_cursor_at": "2026-08-23T10:00:00.000", "source_cursor_id": "row-002"},
        ],
        [],
    ])
    adapter = SocrataProcurementAdapter(
        _config(
            page_size=2,
            id_field="external_id",
            selected_fields=("external_id",),
            cursor_expression=":updated_at",
            cursor_alias="source_cursor_at",
            cursor_id_expression=":id",
            cursor_id_alias="source_cursor_id",
        ),
        session=session,
    )
    adapter.fetch_raw_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))
    second_where = session.calls[1]["params"]["$where"]
    assert ":updated_at = '2026-08-23T10:00:00.000' AND :id > 'row-002'" in second_where
    assert "external_id >" not in second_where


def test_existing_watermark_is_replayed_with_overlap():
    session = FakeSession([[]])
    adapter = SocrataProcurementAdapter(_config(), session=session)
    watermark = SocrataCursor("2026-08-24T10:00:00.000", "X").encode()
    adapter.fetch_raw_incremental(watermark=watermark)
    where = session.calls[0]["params"]["$where"]
    assert "updated_at >= '2026-08-24T09:00:00.000'" in where


def test_max_pages_refuses_to_advance_incomplete_window():
    session = FakeSession([
        [{"id": "A", "updated_at": "2026-08-23T10:00:00.000"}],
    ])
    config = _config(page_size=1, max_pages=1)
    adapter = SocrataProcurementAdapter(config, session=session)
    with pytest.raises(RuntimeError, match="reached max_pages"):
        adapter.fetch_raw_incremental(now=datetime(2026, 8, 24, tzinfo=timezone.utc))


def test_fetch_incremental_runs_country_normalizer():
    session = FakeSession([[{"id": "A", "updated_at": "2026-08-23T10:00:00.000", "title": "works"}]])
    adapter = SocrataProcurementAdapter(_config(page_size=10), session=session)
    rows, _ = adapter.fetch_incremental(
        lambda row: {"source": "X", "external_id": row["id"], "title": row["title"]},
        now=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    assert rows == [{"source": "X", "external_id": "A", "title": "works"}]
