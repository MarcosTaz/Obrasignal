"""Hard-negative and hard-positive guards for shortlist/review quality."""

from company_profile import derive_profile
from opportunity_match_pipeline import evaluate_row


def _profile(cpv_prefixes=None):
    return derive_profile("Construção e reabilitação de pavilhões industriais", {
        "activity": "Construção e reabilitação de pavilhões industriais",
        "contract_interests": [
            "Construção de pavilhões industriais",
            "Reabilitação de coberturas",
        ],
        "coverage_mode": "portugal",
        "countries": ["PRT"],
        "cpv_prefixes": ["45"] if cpv_prefixes is None else cpv_prefixes,
        "keywords": [],
        "min_value": 50_000,
        "max_value": 500_000,
    })


def _row(title, cpv, description=None):
    return {
        "source": "TEST",
        "external_id": title,
        "title": title,
        "description": description or title,
        "buyer": "Município",
        "country": "PRT",
        "cpv": cpv,
        "value": "248000",
        "value_numeric": 248_000,
        "deadline": "2099-12-31",
        "procedure_type": "open procedure",
    }


def test_broad_works_and_open_procedure_cannot_create_review_without_company_evidence():
    result = evaluate_row(
        _row("Empreitada de manutenção de redes de saneamento", "45232410"),
        _profile(),
    )

    # The procurement can look generically attractive by lot-level rules while
    # remaining unproven as a fit for this company's declared work.
    assert result["lot_score"] >= 65
    assert result["capability_evidence"]["status"] == "UNKNOWN"
    assert result["cpv_evidence"]["strength"] == "WEAK"
    assert result["profile_score"] <= 59
    assert result["decision"] == "REJECT"


def test_specific_cpv_can_establish_review_evidence_without_exact_service_phrase():
    result = evaluate_row(
        _row("Empreitada geral", "45213220", "Execução dos trabalhos previstos no caderno de encargos"),
        _profile(["4521"]),
    )

    assert result["capability_evidence"]["status"] == "UNKNOWN"
    assert result["cpv_evidence"]["strength"] == "STRONG"
    assert result["decision"] in {"REVIEW", "QUALIFIED"}


def test_explicit_company_capability_positive_beats_hard_negative_under_same_commercial_conditions():
    negative = evaluate_row(
        _row("Empreitada de manutenção de redes de saneamento", "45232410"),
        _profile(),
    )
    positive = evaluate_row(
        _row(
            "Construção de pavilhão industrial",
            "45213220",
            "Empreitada para construção de pavilhões industriais",
        ),
        _profile(),
    )

    assert positive["capability_evidence"]["status"] == "MATCH"
    assert positive["profile_score"] > negative["profile_score"]
    assert positive["decision"] in {"REVIEW", "QUALIFIED"}
    assert negative["decision"] == "REJECT"
