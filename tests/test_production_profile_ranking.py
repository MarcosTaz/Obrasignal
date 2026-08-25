"""Regressions from the production commercial-ranking evidence in August 2026."""

from company_profile import derive_profile, load_profile, save_profile
from opportunity_match_pipeline import evaluate_row


def production_profile(cpv_prefixes=None):
    return derive_profile("Construção e reabilitação de pavilhões industriais", {
        "activity": "Construção e reabilitação de pavilhões industriais",
        "contract_interests": [
            "Construção de pavilhões industriais",
            "Reabilitação de coberturas",
        ],
        "coverage_mode": "portugal",
        "countries": ["PRT"],
        "cpv_prefixes": ["45", "44", "42", "43"] if cpv_prefixes is None else cpv_prefixes,
        "keywords": [],
        "min_value": 50_000,
        "max_value": 500_000,
    })


def opportunity(title, value, cpv, description=None):
    return {
        "source": "TED",
        "title": title,
        "description": description or title,
        "buyer": "AdRA - Águas da Região de Aveiro, SA",
        "value": value,
        "country": "PRT",
        "cpv": cpv,
        "deadline": "2099-12-31",
    }


def test_production_sewerage_false_positive_is_capped_without_activity_evidence():
    row = opportunity(
        "Portugal – Obras de saneamento – CP/2026/26_DOP - Empreitada de Manutenção de câmaras de visita das redes de águas residuais domésticas",
        248_000,
        "45232410",
    )
    result = evaluate_row(row, production_profile())

    assert result["profile_score"] < 75
    assert result["capability_evidence"]["status"] == "UNKNOWN"
    assert result["cpv_evidence"]["strength"] == "WEAK"
    assert "apenas família CPV genérica" in result["reason"]


def test_production_water_pipe_above_maximum_is_a_hard_economic_mismatch():
    row = opportunity(
        "Portugal – Obras de renovação de condutas de água – Empreitada para substituição de condutas de abastecimento de água",
        650_000,
        "45232150",
    )
    result = evaluate_row(row, production_profile())

    assert result["economic_fit"]["status"] == "UNFAVOURABLE"
    assert result["decision"] == "REJECT"
    assert result["profile_score"] <= 35
    assert "valor acima do máximo definido pela empresa (€500,000)" in result["reason"]


def test_pavilion_and_roof_positive_controls_clearly_beat_unrelated_works():
    unrelated = evaluate_row(opportunity("Obras de saneamento", 248_000, "45232410"), production_profile())
    pavilion = evaluate_row(opportunity(
        "Construção de pavilhão industrial", 250_000, "45213220",
        "Construção de pavilhões industriais",
    ), production_profile())
    roof = evaluate_row(opportunity(
        "Reabilitação de cobertura", 200_000, "45261210",
        "Reabilitação de coberturas",
    ), production_profile())

    assert pavilion["capability_evidence"]["status"] == "MATCH"
    assert roof["capability_evidence"]["status"] == "MATCH"
    assert pavilion["profile_score"] >= 75
    assert roof["profile_score"] >= 75
    assert min(pavilion["profile_score"], roof["profile_score"]) > unrelated["profile_score"]


def test_missing_opportunity_data_remains_unknown_and_cannot_be_high():
    result = evaluate_row({}, production_profile())
    assert result["capability_evidence"]["status"] == "UNKNOWN"
    assert result["economic_fit"]["status"] == "UNKNOWN"
    assert result["cpv_evidence"]["status"] == "UNKNOWN"
    assert result["profile_score"] < 75


def test_specific_cpv_is_stronger_than_a_two_digit_family():
    row = opportunity("Empreitada geral", 250_000, "45213220")
    generic = evaluate_row(row, production_profile(["45"]))
    specific = evaluate_row(row, production_profile(["4521"]))

    assert generic["cpv_evidence"]["strength"] == "WEAK"
    assert specific["cpv_evidence"]["strength"] == "STRONG"
    assert specific["profile_score"] > generic["profile_score"]


def test_persisted_numeric_strings_reach_capability_and_economic_matcher(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "profiles.db"))
    saved = save_profile({**production_profile(), "min_value": "50000", "max_value": "500000"}, account_id="production")
    loaded = load_profile("production")
    result = evaluate_row(opportunity("Renovação de condutas", 650_000, "45232150"), loaded)

    assert saved["min_value"] == 50_000
    assert loaded["max_value"] == 500_000
    assert result["capability"]["min_value"] == 50_000
    assert result["capability"]["max_value"] == 500_000
    assert result["economic_fit"]["status"] == "UNFAVOURABLE"
