"""Decision-quality regressions for deadline precision in relevance scoring."""

from datetime import datetime, timezone

import commercial_score_v2
import opportunity_match_pipeline
from company_profile import derive_profile
from opportunity_match_pipeline import evaluate_row


_FIXED_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return _FIXED_NOW.replace(tzinfo=None)
        return _FIXED_NOW.astimezone(tz)


def _freeze_clock(monkeypatch):
    monkeypatch.setattr(commercial_score_v2, "datetime", _FixedDateTime)
    monkeypatch.setattr(opportunity_match_pipeline, "datetime", _FixedDateTime)


def _profile():
    return derive_profile("Construção de pavilhões industriais", {
        "activity": "Construção de pavilhões industriais",
        "contract_interests": ["Construção de pavilhões industriais"],
        "countries": ["PRT"],
        "cpv_prefixes": ["4521"],
        "keywords": [],
        "min_value": 50_000,
        "max_value": 500_000,
    })


def _row(deadline):
    return {
        "source": "TEST",
        "external_id": "deadline-quality",
        "title": "Construção de pavilhão industrial",
        "description": "Empreitada de construção de pavilhão industrial",
        "buyer": "Município",
        "country": "PRT",
        "cpv": "45213220",
        "value": "250000",
        "value_numeric": 250_000,
        "procedure_type": "open procedure",
        "deadline": deadline,
    }


def test_date_only_today_is_unknown_time_not_expired_or_positive_deadline_evidence(monkeypatch):
    _freeze_clock(monkeypatch)

    result = commercial_score_v2.score_v2(_row("2026-08-25"))

    assert result["deadline_days"] == 0
    assert result["components"]["deadline"] == 0
    assert "prazo hoje; hora não indicada" in result["reasons"]
    assert "prazo terminado" not in result["reasons"]


def test_date_only_deadline_boundary_is_directional_without_midnight_coercion(monkeypatch):
    _freeze_clock(monkeypatch)

    yesterday = commercial_score_v2.score_v2(_row("2026-08-24"))
    today = commercial_score_v2.score_v2(_row("2026-08-25"))
    tomorrow = commercial_score_v2.score_v2(_row("2026-08-26"))

    assert yesterday["deadline_days"] == -1
    assert yesterday["components"]["deadline"] == 0
    assert "prazo terminado" in yesterday["reasons"]
    assert today["components"]["deadline"] == 0
    assert tomorrow["deadline_days"] == 1
    assert tomorrow["components"]["deadline"] == 15
    assert tomorrow["score"] > today["score"]


def test_account_specific_pipeline_does_not_false_reject_date_only_today(monkeypatch):
    _freeze_clock(monkeypatch)

    result = evaluate_row(_row("2026-08-25"), _profile())

    assert "prazo de apresentação terminado" not in result["hard_capability_blockers"]
    assert result["commercial"]["components"]["deadline"] == 0
    assert "prazo hoje; hora não indicada" in result["commercial"]["reasons"]
    assert result["decision"] in {"QUALIFIED", "REVIEW"}


def test_expired_date_and_exact_timestamp_remain_hard_blockers(monkeypatch):
    _freeze_clock(monkeypatch)

    date_only = evaluate_row(_row("2026-08-24"), _profile())
    timestamp = evaluate_row(_row("2026-08-25T11:59:59+00:00"), _profile())

    for result in (date_only, timestamp):
        assert "prazo de apresentação terminado" in result["hard_capability_blockers"]
        assert result["decision"] == "REJECT"
        assert result["profile_score"] <= 35


def test_future_exact_timestamp_remains_non_blocking(monkeypatch):
    _freeze_clock(monkeypatch)

    result = evaluate_row(_row("2026-08-25T12:00:01+00:00"), _profile())

    assert "prazo de apresentação terminado" not in result["hard_capability_blockers"]
