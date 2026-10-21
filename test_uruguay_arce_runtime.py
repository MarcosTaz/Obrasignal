import pytest

from uruguay_arce_runtime import fetch_arce_runtime_batch


def _tender(external_id="tender:1"):
    return {
        "source": "UY_ARCE",
        "signal_type": "TENDER",
        "external_id": external_id,
        "title": "Obra",
    }


def _plan(external_id="pac:1"):
    return {
        "source": "UY_ARCE",
        "signal_type": "PROCUREMENT_PLAN",
        "external_id": external_id,
        "title": "Obra futura",
    }


def test_runtime_batch_keeps_pac_out_of_legacy_projection_but_stages_both_types():
    calls = []

    def tenders(*, watermark):
        calls.append(("rss", watermark))
        return [_tender()], "rss-cursor-2"

    def plans(*, now):
        calls.append(("pac", now))
        return [_plan()]

    batch = fetch_arce_runtime_batch(
        watermark="rss-cursor-1",
        now="now-marker",
        tender_fetcher=tenders,
        plan_fetcher=plans,
    )

    assert calls == [("rss", "rss-cursor-1"), ("pac", "now-marker")]
    assert [row["signal_type"] for row in batch.legacy_tenders] == ["TENDER"]
    assert {(row["signal_type"], row["external_id"]) for row in batch.signals} == {
        ("TENDER", "tender:1"),
        ("PROCUREMENT_PLAN", "pac:1"),
    }
    assert batch.cursor == "rss-cursor-2"


def test_pac_failure_aborts_complete_observation_and_never_returns_tender_cursor():
    def tenders(*, watermark):
        return [_tender()], "cursor-that-must-not-be-staged"

    def plans(*, now):
        raise RuntimeError("PAC unavailable")

    with pytest.raises(RuntimeError, match="PAC unavailable"):
        fetch_arce_runtime_batch(
            watermark="old",
            tender_fetcher=tenders,
            plan_fetcher=plans,
        )


def test_rss_failure_prevents_pac_fetch():
    called = {"pac": False}

    def tenders(*, watermark):
        raise RuntimeError("RSS unavailable")

    def plans(*, now):
        called["pac"] = True
        return [_plan()]

    with pytest.raises(RuntimeError, match="RSS unavailable"):
        fetch_arce_runtime_batch(tender_fetcher=tenders, plan_fetcher=plans)
    assert called["pac"] is False


@pytest.mark.parametrize(
    "records,allowed,label,match",
    [
        ([{"source": "OTHER", "signal_type": "TENDER", "external_id": "1"}], "rss", "tender", "outside UY_ARCE"),
        ([{"source": "UY_ARCE", "signal_type": "AWARD", "external_id": "1"}], "rss", "tender", "unexpected signal_type"),
        ([{"source": "UY_ARCE", "signal_type": "PROCUREMENT_PLAN", "external_id": ""}], "pac", "plan", "without external_id"),
    ],
)
def test_runtime_batch_fails_closed_on_identity_or_type_drift(records, allowed, label, match):
    def tenders(*, watermark):
        return (records if allowed == "rss" else [_tender()]), "cursor"

    def plans(*, now):
        return records if allowed == "pac" else [_plan()]

    with pytest.raises(RuntimeError, match=match):
        fetch_arce_runtime_batch(tender_fetcher=tenders, plan_fetcher=plans)


def test_duplicate_signal_identity_is_deterministic_last_observation_wins():
    first = _plan("pac:7")
    first["title"] = "old"
    second = _plan("pac:7")
    second["title"] = "new"

    batch = fetch_arce_runtime_batch(
        tender_fetcher=lambda *, watermark: ([_tender()], "cursor"),
        plan_fetcher=lambda *, now: [first, second],
    )

    plans = [row for row in batch.signals if row["signal_type"] == "PROCUREMENT_PLAN"]
    assert len(plans) == 1
    assert plans[0]["title"] == "new"
