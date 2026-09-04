from pathlib import Path


SURFACES = (
    Path("factories/industrial-claims/COMMERCIAL_OPERATING_MODEL.md"),
    Path("factories/industrial-claims/DISCOVERY_AND_INTAKE_PACK.md"),
    Path("factories/industrial-claims/GTM_TARGET_ACCOUNT_THESIS.md"),
    Path("factories/industrial-claims/OUTBOUND_PLAYBOOK.md"),
    Path("vertical_apps/industrial_claims/commercial_proof.py"),
    Path("vertical_apps/industrial_claims/leakage_reconciliation.py"),
    Path("vertical_apps/industrial_claims/metadata_triage.py"),
    Path("vertical_apps/industrial_claims/operational_readiness.py"),
    Path("vertical_apps/industrial_claims/public_site/index.html"),
    Path("vertical_apps/industrial_claims/recovery_dossier.py"),
    Path("vertical_apps/industrial_claims/recovery_portfolio.py"),
    Path("vertical_apps/industrial_claims/recovery_portfolio_workflow.py"),
    Path("vertical_apps/industrial_claims/recovery_reconciliation_store.py"),
    Path("vertical_apps/industrial_claims/recovery_workflow.py"),
    Path("vertical_apps/industrial_claims/triage_brief.py"),
)

FORBIDDEN_PROJECT_IDENTITIES = (
    "Certactum",
    "CERTACTUM",
    "certactum.com",
    "marcos@certactum.com",
    "Varactum",
    "VARACTUM",
)


def test_supplier_recovery_surfaces_do_not_reuse_other_project_identity():
    violations = []
    for path in SURFACES:
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_PROJECT_IDENTITIES:
            if forbidden in text:
                violations.append(f"{path}:{forbidden}")
    assert violations == []


def test_retired_working_name_is_never_customer_facing():
    public = Path("vertical_apps/industrial_claims/public_site/index.html").read_text(encoding="utf-8")
    commercial = Path("factories/industrial-claims/COMMERCIAL_OPERATING_MODEL.md").read_text(encoding="utf-8")
    outbound = Path("factories/industrial-claims/OUTBOUND_PLAYBOOK.md").read_text(encoding="utf-8")
    assert "CausLedger" not in public
    assert "CausLedger" not in commercial
    assert "CausLedger" not in outbound


def test_canonical_identity_is_explicit_on_customer_facing_surfaces():
    public = Path("vertical_apps/industrial_claims/public_site/index.html").read_text(encoding="utf-8")
    commercial = Path("factories/industrial-claims/COMMERCIAL_OPERATING_MODEL.md").read_text(encoding="utf-8")
    assert "SUPPLIER RECOVERY" in public
    assert commercial.startswith("# SUPPLIER RECOVERY — COMMERCIAL OPERATING MODEL")
