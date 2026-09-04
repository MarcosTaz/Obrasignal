from pathlib import Path


SITE = Path("vertical_apps/industrial_claims/public_site/index.html")


def test_public_site_matches_metadata_first_supplier_recovery_boundary():
    html = SITE.read_text(encoding="utf-8")

    assert "Certactum" in html
    assert "Supplier-side customer-caused cost &amp; margin recovery" in html
    assert "Request a metadata triage" in html
    assert "Metadata-only first contact" in html
    assert "Do not attach confidential source documents" in html
    assert "Do not email confidential contracts" in html
    assert 'data-release-gate="production-controls-pending"' in html
    assert "cost is not automatically money owed" in html
    assert "supported" in html
    assert "claimed" in html
    assert "approved" in html
    assert "settled" in html


def test_public_site_does_not_present_retired_identity_or_unbounded_claims_scope():
    html = SITE.read_text(encoding="utf-8")

    assert "CausLedger" not in html
    assert "guaranteed recovery" not in html.lower()
    assert "court admissible" not in html.lower()
    assert "send us your contracts" not in html.lower()
    assert "upload your documents" not in html.lower()
    assert "same customer, program and change mechanism" in html
