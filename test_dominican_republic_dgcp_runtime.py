from datetime import datetime, timezone
import json

import pytest

from dominican_republic_dgcp_runtime import DGCPRuntimeCursor, fetch_dgcp_runtime


def _signal(signal_type, external_id):
    return {
        "source": "DO_DGCP",
        "signal_type": signal_type,
        "external_id": external_id,
        "title": external_id,
    }


def _cursor(observation):
    return json.loads(observation.cursor)


def test_first_runtime_observation_combines_all_signals_and_records_daily_pacc():
    seen = {}

    def ocds_fetcher(*, watermark=None, now=None):
        seen["watermark"] = watermark
        return [
            _signal("TENDER", "t-1"),
            _signal("AWARD", "a-1"),
            _signal("CONTRACT", "c-1"),
        ], "cursor-new"

    def pacc_fetcher(*, now=None):
        seen["pacc"] = seen.get("pacc", 0) + 1
        return [_signal("PROCUREMENT_PLAN", "p-1")]

    observation = fetch_dgcp_runtime(
        watermark="cursor-old",
        now=datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
        ocds_fetcher=ocds_fetcher,
        pacc_fetcher=pacc_fetcher,
    )

    assert seen == {"watermark": "cursor-old", "pacc": 1}
    assert observation.pacc_fetched is True
    assert [row["external_id"] for row in observation.legacy_tenders] == ["t-1"]
    assert {row["signal_type"] for row in observation.signals} == {
        "PROCUREMENT_PLAN", "TENDER", "AWARD", "CONTRACT"
    }
    assert _cursor(observation) == {
        "ocds_cursor": "cursor-new",
        "pacc_snapshot_date": "2026-08-25",
    }


def test_second_sync_same_dominican_day_skips_pacc_but_advances_ocds():
    first = DGCPRuntimeCursor(
        ocds_cursor="ocds-old",
        pacc_snapshot_date="2026-08-25",
    ).encode()
    calls = []

    def ocds_fetcher(*, watermark=None, now=None):
        assert watermark == "ocds-old"
        return [_signal("TENDER", "t-2")], "ocds-new"

    def pacc_fetcher(*, now=None):
        calls.append("pacc")
        return [_signal("PROCUREMENT_PLAN", "should-not-run")]

    observation = fetch_dgcp_runtime(
        watermark=first,
        now=datetime(2026, 8, 25, 20, tzinfo=timezone.utc),
        ocds_fetcher=ocds_fetcher,
        pacc_fetcher=pacc_fetcher,
    )
    assert calls == []
    assert observation.pacc_fetched is False
    assert {row["signal_type"] for row in observation.signals} == {"TENDER"}
    assert _cursor(observation) == {
        "ocds_cursor": "ocds-new",
        "pacc_snapshot_date": "2026-08-25",
    }


def test_dominican_midnight_not_utc_midnight_controls_daily_pacc():
    state = DGCPRuntimeCursor(ocds_cursor="old", pacc_snapshot_date="2026-08-25").encode()
    pacc_calls = []

    def ocds_fetcher(*, watermark=None, now=None):
        return [], "new"

    def pacc_fetcher(*, now=None):
        pacc_calls.append(True)
        return []

    # 2026-08-26 02:00 UTC is still 2026-08-25 in Santo Domingo.
    first = fetch_dgcp_runtime(
        watermark=state,
        now=datetime(2026, 8, 26, 2, tzinfo=timezone.utc),
        ocds_fetcher=ocds_fetcher,
        pacc_fetcher=pacc_fetcher,
    )
    assert first.pacc_fetched is False
    assert pacc_calls == []

    # 05:00 UTC is already the next Dominican calendar day.
    second = fetch_dgcp_runtime(
        watermark=first.cursor,
        now=datetime(2026, 8, 26, 5, tzinfo=timezone.utc),
        ocds_fetcher=ocds_fetcher,
        pacc_fetcher=pacc_fetcher,
    )
    assert second.pacc_fetched is True
    assert pacc_calls == [True]
    assert _cursor(second)["pacc_snapshot_date"] == "2026-08-26"


def test_pacc_failure_prevents_observation_and_new_ocds_cursor_escape_when_due():
    def ocds_fetcher(*, watermark=None, now=None):
        return [_signal("TENDER", "t-1")], "must-not-stage"

    def pacc_fetcher(*, now=None):
        raise RuntimeError("pacc failed")

    with pytest.raises(RuntimeError, match="pacc failed"):
        fetch_dgcp_runtime(
            watermark=DGCPRuntimeCursor(ocds_cursor="old", pacc_snapshot_date="2026-08-24").encode(),
            now=datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            ocds_fetcher=ocds_fetcher,
            pacc_fetcher=pacc_fetcher,
        )


def test_ocds_failure_never_calls_pacc():
    called = []

    def ocds_fetcher(*, watermark=None, now=None):
        raise RuntimeError("ocds failed")

    def pacc_fetcher(*, now=None):
        called.append(True)
        return []

    with pytest.raises(RuntimeError, match="ocds failed"):
        fetch_dgcp_runtime(ocds_fetcher=ocds_fetcher, pacc_fetcher=pacc_fetcher)
    assert called == []


def test_legacy_json_ocds_cursor_is_preserved_inside_composite_state():
    legacy = '{"completed_through":"2026-08-24"}'
    seen = []

    def ocds_fetcher(*, watermark=None, now=None):
        seen.append(watermark)
        return [], '{"completed_through":"2026-08-25"}'

    observation = fetch_dgcp_runtime(
        watermark=legacy,
        now=datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
        ocds_fetcher=ocds_fetcher,
        pacc_fetcher=lambda **kwargs: [],
    )
    assert seen == [legacy]
    assert _cursor(observation)["ocds_cursor"] == '{"completed_through":"2026-08-25"}'


def test_future_or_malformed_pacc_snapshot_date_fails_closed():
    future = DGCPRuntimeCursor(ocds_cursor="x", pacc_snapshot_date="2026-08-26").encode()
    with pytest.raises(RuntimeError, match="future PACC"):
        fetch_dgcp_runtime(
            watermark=future,
            now=datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            ocds_fetcher=lambda **kwargs: ([], "x"),
            pacc_fetcher=lambda **kwargs: [],
        )

    malformed = '{"ocds_cursor":"x","pacc_snapshot_date":"not-a-date"}'
    with pytest.raises(RuntimeError, match="invalid pacc_snapshot_date"):
        DGCPRuntimeCursor.decode(malformed)


def test_foreign_source_identity_fails_closed():
    def ocds_fetcher(*, watermark=None, now=None):
        return [{"source": "OTHER", "signal_type": "TENDER", "external_id": "x"}], "c"

    with pytest.raises(RuntimeError, match="foreign source identity"):
        fetch_dgcp_runtime(
            now=datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            ocds_fetcher=ocds_fetcher,
            pacc_fetcher=lambda **kwargs: [],
        )


def test_duplicate_canonical_identity_collapses_without_cross_type_loss():
    duplicate = _signal("TENDER", "same")

    def ocds_fetcher(*, watermark=None, now=None):
        return [duplicate, dict(duplicate), _signal("AWARD", "same")], "c"

    observation = fetch_dgcp_runtime(
        now=datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
        ocds_fetcher=ocds_fetcher,
        pacc_fetcher=lambda **kwargs: [],
    )
    assert len(observation.signals) == 2
    assert {row["signal_type"] for row in observation.signals} == {"TENDER", "AWARD"}
