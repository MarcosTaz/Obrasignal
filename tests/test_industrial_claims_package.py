from datetime import date

from vertical_apps.industrial_claims.package import build_claim_package
from vertical_apps.industrial_claims.service import CLAIM_CURRENCY_EVIDENCE, NOTICE_DEADLINE_EVIDENCE, IndustrialClaimsService


def _documents():
    return dict(
        commercial_basis_content="signed supply agreement and purchase order terms",
        event_evidence_content="documented cancellation or reduction event",
        cost_evidence_content="invoice and cost ledger supporting the exposure",
    )


def test_claim_package_is_evidence_indexed_and_never_overclaims(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="cancel-1",
        claim_family="TOOLING", commercial_basis_ref="po-1", cost_evidence_ref="invoice-1", currency="EUR",
        gross_cost="50000", prior_payment="10000", notice_due=date(2026, 9, 30), **_documents(),
    )
    package = build_claim_package(result, customer_ref="oem-1", program_ref="program-1", event_ref="cancel-1")
    assert package["schema_version"] == 4
    assert package["net_potential"] == "40000"
    assert package["currency"] == "EUR"
    assert package["calculation"]["output_unit"] == "EUR"
    assert package["economic_truth_state"] == "DOCUMENTED_CANDIDATE_FOR_REVIEW"
    assert package["entitlement"]["confidence"] == "PARTIAL"
    assert package["entitlement"]["rule_ref"] == "documented-commercial-basis-v3-pre-review"
    assert package["entitlement"]["recoverability_established"] is False
    assert package["notice"] == {"truth_state": "DECLARED_DATE_FOR_REVIEW", "due_date": "2026-09-30"}
    assert package["customer_action_authorized"] is False
    assert package["legal_conclusion"] is None
    assert len(package["evidence_index"]) == 3
    assert all(item["content_hash"] for item in package["evidence_index"])
    assert {item["verification_state"] for item in package["evidence_index"]} == {"CONTENT_HASHED"}
    assert {item["raw_content_persisted"] for item in package["evidence_index"]} == {"false"}


def test_missing_evidence_package_stays_potential_entitlement(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="reduction-1",
        claim_family="FINISHED_GOODS", commercial_basis_ref="contract-1", cost_evidence_ref="inventory-1", currency="EUR",
        gross_cost="75000", missing_evidence=("ownership", "release_history"), **_documents(),
    )
    package = build_claim_package(result, customer_ref="oem-1", program_ref="program-1", event_ref="reduction-1")
    assert package["economic_truth_state"] == "POTENTIAL_ENTITLEMENT"
    assert package["currency"] == "EUR"
    assert package["entitlement"]["confidence"] == "UNRESOLVED"
    assert package["entitlement"]["recoverability_established"] is False
    assert package["notice"] == {"truth_state": "UNKNOWN", "due_date": None}
    assert package["missing_evidence"] == [NOTICE_DEADLINE_EVIDENCE, "ownership", "release_history"]
    assert {item["verification_state"] for item in package["evidence_index"]} == {"CONTENT_HASHED"}


def test_reference_only_package_cannot_claim_evidence_supported(tmp_path):
    service = IndustrialClaimsService(tmp_path / "reference-only.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="reference-only",
        claim_family="TOOLING", commercial_basis_ref="po-reference", cost_evidence_ref="ledger-reference", currency="EUR",
        gross_cost="10000", notice_deadline_not_applicable=True,
    )
    package = build_claim_package(result, customer_ref="oem-1", program_ref="program-1", event_ref="reference-only")
    assert package["economic_truth_state"] == "POTENTIAL_ENTITLEMENT"
    assert package["currency"] == "EUR"
    assert package["entitlement"]["confidence"] == "UNRESOLVED"
    assert package["entitlement"]["recoverability_established"] is False
    assert {item["verification_state"] for item in package["evidence_index"]} == {"REFERENCE_ONLY"}
    assert package["customer_action_authorized"] is False
    assert package["legal_conclusion"] is None


def test_missing_currency_is_never_fabricated_in_package(tmp_path):
    service = IndustrialClaimsService(tmp_path / "missing-currency.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="no-currency",
        claim_family="WIP", commercial_basis_ref="po-no-currency", cost_evidence_ref="ledger-no-currency",
        gross_cost="10000", notice_deadline_not_applicable=True, **_documents(),
    )
    package = build_claim_package(result, customer_ref="oem-1", program_ref="program-1", event_ref="no-currency")
    assert package["currency"] is None
    assert package["calculation"]["output_unit"] == "UNKNOWN"
    assert CLAIM_CURRENCY_EVIDENCE in package["missing_evidence"]
    assert package["entitlement"]["confidence"] == "UNRESOLVED"
    assert package["economic_truth_state"] == "POTENTIAL_ENTITLEMENT"
