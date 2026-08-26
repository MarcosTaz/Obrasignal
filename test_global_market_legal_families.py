from global_market_legal_families import (
    COUNTRY_FAMILY_LEGAL_STATE,
    TED_EFORMS_LEGAL,
    compare_legal_fingerprint,
    revalidation_required,
)
from market_scope_registry import SHARED_FAMILIES


def test_ted_green_is_source_scoped_across_exact_23_shared_markets():
    assert TED_EFORMS_LEGAL.classification == "LEGAL_GREEN"
    assert set(TED_EFORMS_LEGAL.countries) == set(SHARED_FAMILIES["TED_EFORMS"])
    assert len(COUNTRY_FAMILY_LEGAL_STATE) == 23
    assert set(COUNTRY_FAMILY_LEGAL_STATE.values()) == {"LEGAL_GREEN"}
    assert "does not prove" in TED_EFORMS_LEGAL.scope_limit


def test_ted_legal_evidence_captures_commercial_reuse_and_anonymous_search_api():
    assert "commercial" in TED_EFORMS_LEGAL.commercial_reuse
    assert "anonymous" in TED_EFORMS_LEGAL.api_terms
    assert "CC BY 4.0" in TED_EFORMS_LEGAL.license_type
    assert "CC0 1.0" in TED_EFORMS_LEGAL.license_type
    assert TED_EFORMS_LEGAL.evidence_fingerprint.startswith("sha256:")


def test_legal_change_watch_fails_closed_on_missing_or_changed_fingerprint():
    fp = TED_EFORMS_LEGAL.evidence_fingerprint
    assert compare_legal_fingerprint(fp, fp) == "UNCHANGED"
    assert compare_legal_fingerprint(fp, "sha256:different") == "MATERIAL_CHANGE"
    assert compare_legal_fingerprint(fp, None) == "UNKNOWN"
    assert compare_legal_fingerprint(None, fp) == "UNKNOWN"


def test_previous_green_requires_revalidation_if_change_or_current_evidence_missing():
    fp = TED_EFORMS_LEGAL.evidence_fingerprint
    assert revalidation_required("LEGAL_GREEN", fp, fp) is False
    assert revalidation_required("LEGAL_GREEN", fp, "sha256:different") is True
    assert revalidation_required("LEGAL_GREEN", fp, None) is True
    assert revalidation_required("LEGAL_AMBER", fp, "sha256:different") is False
