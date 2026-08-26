"""Change-impact composition probe for #458 deadline semantics × #466 explanation truth."""

from datetime import datetime, timezone

import commercial_score_v2
import opportunity_match_pipeline
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
    return {
        "account_id": "composition-test",
        "activity": "",
        "contract_interests": [],
        "keywords": [],
        "exclude_keywords": [],
        "countries": [],
        "cpv_prefixes": [],
        "min_value": None,
        "max_value": None,
        "economic_min_score": 0,
        "preferred_procedure_types": [],
        "excluded_procedure_types": [],
        "regions": [],
        "geographic_radius_km": None,
        "services": [],
        "capability_tags": [],
        "project_scales": [],
        "certifications": [],
        "hard_exclusions": [],
    }


def _row(deadline):
    return {
        "source": "TEST",
        "external_id": f"deadline:{deadline}",
        "title": "Contrato genérico",
        "description": "",
        "buyer": "",
        "country": "",
        "cpv": "",
        "value": "",
        "value_numeric": None,
        "procedure_type": "",
        "deadline": deadline,
    }


def _blocker_reasons(result):
    return [factor["reason"] for factor in result["explanation"]["negative_factors"]]


def test_date_only_today_has_no_stale_expired_explanation(monkeypatch):
    _freeze_clock(monkeypatch)

    result = evaluate_row(_row("2026-08-25"), _profile())

    assert "prazo hoje; hora não indicada" in result["commercial"]["reasons"]
    assert "prazo terminado" not in result["commercial"]["reasons"]
    assert "prazo de apresentação terminado" not in result["hard_capability_blockers"]
    assert "prazo de apresentação terminado" not in _blocker_reasons(result)


def test_date_only_expired_still_surfaces_as_negative_explanation(monkeypatch):
    _freeze_clock(monkeypatch)

    result = evaluate_row(_row("2026-08-24"), _profile())

    assert "prazo de apresentação terminado" in result["hard_capability_blockers"]
    assert "prazo de apresentação terminado" in _blocker_reasons(result)


def test_exact_past_timestamp_still_surfaces_as_negative_explanation(monkeypatch):
    _freeze_clock(monkeypatch)

    result = evaluate_row(_row("2026-08-25T11:59:59+00:00"), _profile())

    assert "prazo de apresentação terminado" in result["hard_capability_blockers"]
    assert "prazo de apresentação terminado" in _blocker_reasons(result)


def test_exact_future_timestamp_has_no_expired_explanation(monkeypatch):
    _freeze_clock(monkeypatch)

    result = evaluate_row(_row("2026-08-25T12:00:01+00:00"), _profile())

    assert "prazo de apresentação terminado" not in result["hard_capability_blockers"]
    assert "prazo de apresentação terminado" not in _blocker_reasons(result)


def test_unknown_deadline_does_not_invent_open_or_expired_temporal_claim(monkeypatch):
    _freeze_clock(monkeypatch)

    result = evaluate_row(_row("not-a-date"), _profile())
    rendered = " ".join(
        str(factor.get("reason") or "")
        for factor in result["explanation"]["factors"] + result["explanation"]["negative_factors"]
    ).lower()

    assert "prazo de apresentação terminado" not in rendered
    assert "prazo aberto" not in rendered
    assert "urgente" not in rendered
