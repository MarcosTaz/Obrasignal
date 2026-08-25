from pathlib import Path


ROOT = Path(__file__).resolve().parent
PRINCIPLE = ROOT / "PRIVACY_NON_INTRUSION_PRINCIPLE.md"


def _text():
    return PRINCIPLE.read_text(encoding="utf-8")


def test_privacy_non_intrusion_is_a_permanent_cross_cutting_constraint():
    text = _text()
    assert "permanent cross-cutting product and architecture constraint" in text
    assert "Minimum data required, maximum intelligence extracted." in text
    assert "public data plus the smallest practical amount" in text


def test_deep_integrations_are_optional_granular_reversible_and_least_privilege():
    text = _text()
    for requirement in (
        "optional",
        "granular",
        "purpose-bound",
        "reversible",
        "inspectable",
        "proportionate",
        "least-privilege",
    ):
        assert f"**{requirement}**" in text


def test_sensitive_system_access_is_not_assumed():
    text = _text()
    for forbidden_default in (
        "bank accounts",
        "accounting ledgers",
        "payroll",
        "email inboxes",
        "continuous GPS/location",
    ):
        assert forbidden_default in text


def test_material_recommendations_must_expose_data_provenance():
    text = _text()
    assert "which public sources were used" in text
    assert "which company-provided facts were used" in text
    assert "which integration-derived facts were used" in text
    assert "what changes if an optional data source is removed or unavailable" in text


def test_company_confidential_data_is_isolated_and_workforce_tracking_is_non_intrusive():
    text = _text()
    assert "Information identifiable to one company must not be used improperly to benefit another company" in text
    assert "Continuous worker GPS is not a default sensor" in text
    assert "employee punishment or ranking system" in text


def test_shadow_and_action_do_not_turn_data_access_into_pressure_or_authority():
    text = _text()
    assert "SHADOW must tolerate incomplete company data" in text
    assert "ACTION authorization and data authorization are separate" in text
    assert "Permission to read a data source does not imply permission to contact, purchase, negotiate, book, commit funds or create legal obligations" in text


def test_privacy_failure_blocks_capability_promotion():
    text = _text()
    assert "Failure on a material privacy/non-intrusion question blocks promotion until redesigned" in text
