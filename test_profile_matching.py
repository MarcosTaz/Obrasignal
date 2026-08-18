"""Behavioral tests for profile -> opportunity matching."""
from profile_scoring import personalized_score


def profile():
    return {
        "activity": "estruturas metálicas, pavilhões e serralharia industrial",
        "countries": ["PT", "ES", "FR"],
        "keywords": ["estruturas metálicas", "pavilhões", "serralharia industrial"],
        "exclude_keywords": ["arquitetura", "fiscalização"],
        "cpv_prefixes": ["4522"],
        "min_value": 100000,
        "max_value": 2000000,
    }


def score_with(row, monkeypatch):
    monkeypatch.setattr("profile_scoring.load_profile", lambda: profile())
    return personalized_score(row, base_score=70)


def test_strong_match(monkeypatch):
    score, label, *_ = score_with({
        "title": "Construção de pavilhão industrial em estruturas metálicas",
        "description": "Fabrico e montagem de estrutura metálica",
        "buyer": "Município",
        "country": "ES",
        "cpv": "45223200",
        "value": "850000",
    }, monkeypatch)
    assert score >= 90
    assert label == "ALERTA MÁXIMO"


def test_excluded_service_is_penalized(monkeypatch):
    score, *_ = score_with({
        "title": "Serviços de arquitetura e fiscalização de obra",
        "description": "Projeto e fiscalização",
        "buyer": "Município",
        "country": "ES",
        "cpv": "71200000",
        "value": "400000",
    }, monkeypatch)
    assert score < 75


def test_unpreferred_country_loses_country_bonus(monkeypatch):
    preferred, *_ = score_with({"title": "Estruturas metálicas", "country": "ES", "cpv": "45220000", "value": "500000"}, monkeypatch)
    other, *_ = score_with({"title": "Estruturas metálicas", "country": "DE", "cpv": "45220000", "value": "500000"}, monkeypatch)
    assert preferred > other
