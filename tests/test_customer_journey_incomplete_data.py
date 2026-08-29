from pathlib import Path

from company_profile_validation import validate_company_profile


ROOT = Path(__file__).resolve().parents[1]


def test_advanced_profile_validation_produces_actionable_field_errors():
    errors = validate_company_profile({
        "countries": ["PRT"],
        "cpv_prefixes": ["X5", "4"],
        "economic_min_score": 60,
    })
    assert "cpv_prefixes: prefixo inválido 'X5'." in errors
    assert "cpv_prefixes: prefixo inválido '4'." in errors


def test_mobile_onboarding_surfaces_server_validation_details_instead_of_error_code():
    source = (ROOT / "mobile" / "components" / "ProfileOnboarding.js").read_text(encoding="utf-8")
    assert "err?.responseBody?.detail?.errors" in source
    assert "Array.isArray(details)&&details.length" in source
    assert "details.join('\\n')" in source
    assert "setError(profileErrorMessage(err))" in source


def test_mobile_onboarding_cannot_complete_without_authoritative_saved_profile():
    source = (ROOT / "mobile" / "components" / "ProfileOnboarding.js").read_text(encoding="utf-8")
    assert "if(!result?.profile)" in source
    assert "onComplete(result.profile)" in source
    assert "result?.profile||draft" not in source
    assert "servidor não confirmou o perfil guardado" in source
