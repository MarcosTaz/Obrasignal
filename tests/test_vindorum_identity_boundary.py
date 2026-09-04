from pathlib import Path


FACTORY_ROOT = Path("factories/industrial-claims")
VERTICAL_ROOT = Path("vertical_apps/industrial_claims")
TEXT_SUFFIXES = {".py", ".md", ".json", ".html", ".txt", ".toml", ".yml", ".yaml"}

# Build retired/foreign identities from fragments so this regression test does not
# itself become a searchable copy of a retired brand phrase.
RETIRED_PRODUCT = (
    "Supplier" + " Recovery",
    "SUPPLIER" + "_RECOVERY",
    "supplier" + "_recovery",
)
LEGACY_INTERNAL = (
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

# Historical internal implementation/schema names may remain only in these modules
# until they can be migrated without breaking stored proof/API compatibility. They
# are never accepted as company identity or on customer-facing surfaces. The list
# is intentionally explicit so legacy naming cannot spread to new files.
LEGACY_COMPATIBILITY_FILES = {
    VERTICAL_ROOT / "change_capture.py",
    VERTICAL_ROOT / "change_capture_reminder.py",
    VERTICAL_ROOT / "change_capture_web.py",
    VERTICAL_ROOT / "change_chronology_reader.py",
    VERTICAL_ROOT / "change_sheet_trust.py",
    VERTICAL_ROOT / "change_supplement.py",
    VERTICAL_ROOT / "counterparty_acknowledgement.py",
    VERTICAL_ROOT / "dossier.py",
    VERTICAL_ROOT / "durable_proof.py",
    VERTICAL_ROOT / "evidence_escrow_provider.py",
    VERTICAL_ROOT / "offline_export_audit.py",
    VERTICAL_ROOT / "offline_export_bundle.py",
    VERTICAL_ROOT / "original_worm_store.py",
    VERTICAL_ROOT / "proof.py",
    VERTICAL_ROOT / "proof_attestation_archive.py",
    VERTICAL_ROOT / "proof_extensions.py",
    VERTICAL_ROOT / "proof_externalization.py",
    VERTICAL_ROOT / "proof_externalization_audit.py",
    VERTICAL_ROOT / "proof_externalization_integrity.py",
    VERTICAL_ROOT / "proof_externalization_web.py",
    VERTICAL_ROOT / "proof_package.py",
    VERTICAL_ROOT / "proof_service.py",
    VERTICAL_ROOT / "proof_verifier.py",
    VERTICAL_ROOT / "public_verification.py",
    VERTICAL_ROOT / "public_verification_store.py",
    VERTICAL_ROOT / "public_verification_web.py",
    VERTICAL_ROOT / "recovery_dossier.py",
    VERTICAL_ROOT / "s3_worm_backend.py",
    VERTICAL_ROOT / "secure_capture_registry.py",
    VERTICAL_ROOT / "secure_outcome_registry.py",
    VERTICAL_ROOT / "semantic_diff_signature.py",
    VERTICAL_ROOT / "web.py",
    VERTICAL_ROOT / "worm_lock_provider.py",
}


def _surface_files():
    for root in (FACTORY_ROOT, VERTICAL_ROOT):
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def test_foreign_and_retired_company_identities_are_absent_everywhere():
    violations = []
    for path in _surface_files():
        text = path.read_text(encoding="utf-8")
        for forbidden in RETIRED_PRODUCT + FOREIGN:
            if forbidden in text:
                violations.append(f"{path}:{forbidden}")
    assert violations == []


def test_legacy_internal_name_is_bounded_and_never_customer_facing():
    violations = []
    legacy_files = set()
    for path in _surface_files():
        text = path.read_text(encoding="utf-8")
        if any(value in text for value in LEGACY_INTERNAL):
            legacy_files.add(path)
            if path not in LEGACY_COMPATIBILITY_FILES:
                violations.append(f"legacy identity outside compatibility allowlist: {path}")
            if path.is_relative_to(FACTORY_ROOT) or "public_site" in path.parts or "templates" in path.parts:
                violations.append(f"legacy identity on customer-facing surface: {path}")
    assert violations == []
    assert legacy_files <= LEGACY_COMPATIBILITY_FILES


def test_customer_visible_runtime_outputs_are_vindorum_only():
    change_web = (VERTICAL_ROOT / "change_capture_web.py").read_text(encoding="utf-8")
    change_capture = (VERTICAL_ROOT / "change_capture.py").read_text(encoding="utf-8")
    supplement = (VERTICAL_ROOT / "change_supplement.py").read_text(encoding="utf-8")
    proof_web = (VERTICAL_ROOT / "proof_externalization_web.py").read_text(encoding="utf-8")
    offline_bundle = (VERTICAL_ROOT / "offline_export_bundle.py").read_text(encoding="utf-8")
    verifier = (VERTICAL_ROOT / "proof_verifier.py").read_text(encoding="utf-8")
    secure_web = (VERTICAL_ROOT / "secure_intake_web.py").read_text(encoding="utf-8")

    legacy_title = "Caus" + "Ledger"
    legacy_upper = "CAUS" + "LEDGER"
    legacy_lower = "caus" + "ledger"
    foreign_lower = "cert" + "actum"

    for text in (change_web, proof_web):
        assert f"X-{legacy_title}" not in text
        assert f'filename="{legacy_title}' not in text
        assert f'filename="{legacy_lower}' not in text

    assert foreign_lower not in secure_web.lower()
    assert 'provider="vindorum-secure-intake"' in secure_web
    assert 'Blueprint("vindorum_secure_intake"' in secure_web

    assert "X-VINDORUM-Sheet-SHA256" in change_web
    assert 'filename="vindorum-change-' in change_web
    assert 'filename="vindorum-late-change-supplement.txt' in change_web
    assert "VINDORUM — CHANGE CAPTURE SHEET" in change_capture
    assert legacy_upper + " — CHANGE CAPTURE SHEET" not in change_capture
    assert "VINDORUM — LATE CHANGE SUPPLEMENT" in supplement
    assert legacy_upper + " — LATE CHANGE SUPPLEMENT" not in supplement

    assert "X-VINDORUM-Confidential" in proof_web
    assert 'filename="vindorum-offline-' in proof_web
    assert '"deliverable": "VINDORUM_CONFIDENTIAL_OFFLINE_VERIFICATION_BUNDLE"' in offline_bundle
    assert legacy_upper + "_CONFIDENTIAL_OFFLINE_VERIFICATION_BUNDLE" not in offline_bundle
    assert "independently_verifiable_without_vindorum" in verifier
    assert "independently_verifiable_without_" + legacy_lower not in verifier
    assert "DO NOT TRUST VINDORUM STATE LABELS" in verifier
    assert "DO NOT TRUST " + legacy_upper + " STATE LABELS" not in verifier


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
