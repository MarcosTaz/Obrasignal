from company_profile import DEFAULT_PROFILE, derive_profile
from opportunity_match_pipeline import evaluate_row


def _generic_works_row():
    return {
        "source": "SYNTHETIC",
        "external_id": "INTEL-COLD-START-1",
        "title": "Empreitada geral de construção",
        "description": "Empreitada de construção e manutenção",
        "buyer": "Município",
        "cpv": "45210000",
        "value": "150000",
        "country": "PRT",
        "deadline": "2099-12-31",
        "procedure_type": "open",
    }


def test_sparse_default_profile_cannot_promote_generic_market_fit_to_review():
    """Broad market heuristics are not evidence of company-specific relevance."""
    profile = dict(DEFAULT_PROFILE)
    result = evaluate_row(_generic_works_row(), profile)

    assert result["capability_evidence"]["matched"] is False
    assert result["cpv_evidence"]["strength"] != "STRONG"
    assert result["profile_score"] < 60
    assert result["decision"] == "REJECT"


def test_explicit_company_evidence_can_still_promote_a_specific_match():
    profile = derive_profile(
        "construção e reabilitação",
        {
            **DEFAULT_PROFILE,
            "activity": "construção e reabilitação",
            "contract_interests": ["empreitada de construção"],
            "services": ["empreitada de construção"],
            "cpv_prefixes": ["4521"],
            "min_value": 50_000,
            "max_value": 500_000,
        },
    )
    result = evaluate_row(_generic_works_row(), profile)

    assert result["capability_evidence"]["matched"] is True
    assert result["cpv_evidence"]["strength"] == "STRONG"
    assert result["decision"] in {"REVIEW", "QUALIFIED"}
