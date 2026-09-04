from pathlib import Path


CUSTOMER_SURFACES = (
    Path("vertical_apps/industrial_claims/public_site/index.html"),
    Path("factories/industrial-claims/BRAND_IDENTITY.md"),
    Path("factories/industrial-claims/COMMERCIAL_OPERATING_MODEL.md"),
    Path("factories/industrial-claims/FACTORY_STATE.md"),
    Path("factories/industrial-claims/CURRENT_BATON.md"),
)

OTHER_PROJECT_IDENTITIES = ("CERTACTUM", "Certactum", "certactum.com", "VARACTUM", "Varactum", "obrasignal.com")
RETIRED_BRAND = "Supplier Recovery"


def test_vindorum_is_canonical_on_company_surfaces():
    for path in CUSTOMER_SURFACES:
        text = path.read_text(encoding="utf-8")
        assert "VINDORUM" in text, path
        assert RETIRED_BRAND not in text, path


def test_customer_surfaces_do_not_reuse_other_project_identity():
    violations = []
    for path in CUSTOMER_SURFACES:
        text = path.read_text(encoding="utf-8")
        for forbidden in OTHER_PROJECT_IDENTITIES:
            if forbidden in text:
                violations.append(f"{path}:{forbidden}")
    assert violations == []


def test_billing_namespace_is_vindorum_only():
    text = Path("vertical_apps/industrial_claims/billing_state.py").read_text(encoding="utf-8")
    assert "vindorum_billing_state" in text
    assert "vindorum_account_id" in text
    assert "certactum_billing_state" not in text
    assert "certactum_billing_events" not in text
