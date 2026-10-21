from global_market_shared_legal_evidence import (
    ECUADOR,
    PARAGUAY,
    SHARED_PUBLISHER_LEGAL_EVIDENCE,
    SOUTH_AFRICA,
    URUGUAY,
)


def test_explicit_shared_publisher_licences_are_source_scoped_green():
    assert set(SHARED_PUBLISHER_LEGAL_EVIDENCE) == {
        "Ecuador", "Paraguay", "South Africa", "Uruguay"
    }
    for row in (ECUADOR, PARAGUAY, SOUTH_AFRICA):
        assert row.classification == "LEGAL_GREEN"
        assert row.commercial_reuse == "PROVEN"
        assert row.redistribution == "PROVEN"
        assert row.derivative_use == "PROVEN"
        assert row.semantic_fingerprint.startswith("sha256:")


def test_ecuador_keeps_embedded_ocds_licence_scope():
    assert "CC BY 3.0 Ecuador" in ECUADOR.licence
    assert "OCDS" in ECUADOR.selected_source_slice
    assert "not proof" in ECUADOR.exact_scope_limit


def test_paraguay_separates_legal_green_from_oauth_technical_contract():
    assert "CC BY 4.0" in PARAGUAY.licence
    assert "OAuth" in PARAGUAY.exact_scope_limit


def test_south_africa_keeps_explicit_subset_completeness_caveat():
    assert "CC BY 4.0" in SOUTH_AFRICA.licence
    assert "subset" in SOUTH_AFRICA.exact_scope_limit
    assert "complete" in SOUTH_AFRICA.exact_scope_limit


def test_uruguay_does_not_infer_historical_open_data_licence_onto_live_transport():
    assert URUGUAY.classification == "LEGAL_AMBER"
    assert URUGUAY.commercial_reuse == "PARTIAL"
    assert "RSS + Record/Release" in URUGUAY.selected_source_slice
    assert "not yet captured" in URUGUAY.exact_scope_limit
