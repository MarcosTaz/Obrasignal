from pathlib import Path


FACTORY_ROOT = Path("factories/industrial-claims")
VERTICAL_ROOT = Path("vertical_apps/industrial_claims")
TEXT_SUFFIXES = {".py", ".md", ".json", ".html", ".txt", ".toml", ".yml", ".yaml"}

# Build retired/foreign identities from fragments so this regression test does not
# itself become a searchable copy of a retired brand phrase.
RETIRED = (
    "Supplier" + " Recovery",
    "SUPPLIER" + "_RECOVERY",
    "supplier" + "_recovery",
    "Caus" + "Ledger",
    "CAUS" + "LEDGER",
    "caus" + "ledger",
)
FOREIGN = (
    "CERT" + "ACTUM",
    "Cert" + "actum",
    "cert" + "actum.com",
    "VAR" + "ACTUM",
    "Var" + "actum",
    "obra" + "signal.com",
)


def _surface_files():
    for root in (FACTORY_ROOT, VERTICAL_ROOT):
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def test_vindorum_is_the_only_company_identity_across_its_factory_and_vertical():
    violations = []
    for path in _surface_files():
        text = path.read_text(encoding="utf-8")
        for forbidden in RETIRED + FOREIGN:
            if forbidden in text:
                violations.append(f"{path}:{forbidden}")
    assert violations == []


def test_canonical_vindorum_identity_exists_on_primary_customer_surfaces():
    primary = (
        Path("vertical_apps/industrial_claims/public_site/index.html"),
        FACTORY_ROOT / "BRAND_IDENTITY.md",
        FACTORY_ROOT / "COMMERCIAL_OPERATING_MODEL.md",
        FACTORY_ROOT / "FACTORY_STATE.md",
        FACTORY_ROOT / "CURRENT_BATON.md",
        FACTORY_ROOT / "DISCOVERY_AND_INTAKE_PACK.md",
        FACTORY_ROOT / "DOSSIER_STANDARD.md",
    )
    for path in primary:
        assert "VINDORUM" in path.read_text(encoding="utf-8"), path


def test_billing_namespace_is_vindorum_only():
    text = (VERTICAL_ROOT / "billing_state.py").read_text(encoding="utf-8")
    assert "vindorum_billing_state" in text
    assert "vindorum_billing_events" in text
    assert "vindorum_account_id" in text
    assert "cert" + "actum_billing_state" not in text
    assert "cert" + "actum_billing_events" not in text
