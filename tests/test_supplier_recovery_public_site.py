from pathlib import Path


SITE = Path("vertical_apps/industrial_claims/public_site/index.html")


def test_public_site_matches_metadata_first_supplier_recovery_boundary():
    html = SITE.read_text(encoding="utf-8")
    assert "SUPPLIER RECOVERY" in html
    assert "SUPPLIER-SIDE CUSTOMER/OEM-CAUSED COST &amp; MARGIN RECOVERY" in html
    assert "Metadata-only first contact" in html
    assert "Do not attach confidential source documents" in html
    assert "Do not email confidential contracts" in html
    assert 'data-release-gate="production-controls-pending"' in html
    assert "Cost is not automatically money owed" in html
    assert "Supported · unclaimed" in html
    assert "Claimed · unapproved" in html
    assert "Approved · unsettled" in html
    assert "NO CLAIM / NEEDS REVIEW" in html
    assert "what still requires review" in html
    assert "what the available evidence does not support" in html


def test_public_site_does_not_present_other_project_identity_or_unbounded_claims_scope():
    html = SITE.read_text(encoding="utf-8")
    assert "Certactum" not in html
    assert "Varactum" not in html
    assert "CausLedger" not in html
    assert "certactum.com" not in html
    assert "guaranteed recovery" not in html.lower()
    assert "court admissible" not in html.lower()
    assert "send us your contracts" not in html.lower()
    assert "upload your documents" not in html.lower()
