import pytest

from dominican_republic_dgcp_runtime import fetch_dgcp_runtime


def _signal(signal_type, external_id):
    return {
        "source": "DO_DGCP",
        "signal_type": signal_type,
        "external_id": external_id,
        "title": external_id,
    }


def test_runtime_combines_all_signals_but_legacy_projects_only_tenders():
    seen = {}

    def ocds_fetcher(*, watermark=None, now=None):
        seen["watermark"] = watermark
        return [
            _signal("TENDER", "t-1"),
            _signal("AWARD", "a-1"),
            _signal("CONTRACT", "c-1"),
        ], "cursor-new"

    def pacc_fetcher(*, now=None):
        return [_signal("PROCUREMENT_PLAN", "p-1")]

    observation = fetch_dgcp_runtime(
        watermark="cursor-old",
        ocds_fetcher=ocds_fetcher,
        pacc_fetcher=pacc_fetcher,
    )

    assert seen["watermark"] == "cursor-old"
    assert observation.cursor == "cursor-new"
    assert [row["external_id"] for row in observation.legacy_tenders] == ["t-1"]
    assert {row["signal_type"] for row in observation.signals} == {
        "PROCUREMENT_PLAN", "TENDER", "AWARD", "CONTRACT"
    }


def test_pacc_failure_prevents_an_observation_and_cursor_escape():
    def ocds_fetcher(*, watermark=None, now=None):
        return [_signal("TENDER", "t-1")], "must-not-stage"

    def pacc_fetcher(*, now=None):
        raise RuntimeError("pacc failed")

    with pytest.raises(RuntimeError, match="pacc failed"):
        fetch_dgcp_runtime(
            watermark="old",
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


def test_foreign_source_identity_fails_closed():
    def ocds_fetcher(*, watermark=None, now=None):
        return [{"source": "OTHER", "signal_type": "TENDER", "external_id": "x"}], "c"

    with pytest.raises(RuntimeError, match="foreign source identity"):
        fetch_dgcp_runtime(
            ocds_fetcher=ocds_fetcher,
            pacc_fetcher=lambda **kwargs: [],
        )


def test_duplicate_canonical_identity_collapses_without_cross_type_loss():
    duplicate = _signal("TENDER", "same")

    def ocds_fetcher(*, watermark=None, now=None):
        return [duplicate, dict(duplicate), _signal("AWARD", "same")], "c"

    observation = fetch_dgcp_runtime(
        ocds_fetcher=ocds_fetcher,
        pacc_fetcher=lambda **kwargs: [],
    )
    assert len(observation.signals) == 2
    assert {row["signal_type"] for row in observation.signals} == {"TENDER", "AWARD"}
