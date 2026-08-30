from dataclasses import replace
from datetime import date

import pytest

from vertical_apps.industrial_claims.amendment import amend_case
from vertical_apps.industrial_claims.package import build_claim_package
from vertical_apps.industrial_claims.service import CLAIM_CURRENCY_EVIDENCE, NOTICE_DEADLINE_EVIDENCE, IndustrialClaimsService


def _documents():
    return dict(
        commercial_basis_content="signed supply agreement and purchase order terms",
        event_evidence_content="documented cancellation or reduction event",
        cost_evidence_content="invoice and cost ledger supporting the exposure",
    )


def _package_result(tmp_path):
    service = IndustrialClaimsService(tmp_path / "package-identity.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="cancel-1",
        claim_family="TOOLING", commercial_basis_ref="po-1", cost_evidence_ref="invoice-1", currency="EUR",
        gross_cost="50000", notice_deadline_not_applicable=True, **_documents(),
    )
    return service, result


def test_claim_package_is_evidence_indexed_and_never_overclaims(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="cancel-1",
        claim_family="TOOLING", commercial_basis_ref="po-1", cost_evidence_ref="invoice-1", currency="EUR",
        gross_cost="50000", prior_payment="10000", notice_due=date(2026, 9, 30), **_documents(),
    )
    package = build_claim_package(
        service, result,
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="cancel-1",
        as_of_date=date(2026, 9, 29),
    )
    assert package["schema_version"] == 7
    assert package["customer_ref"] == "oem-1"
    assert package["program_ref"] == "program-1"
    assert package["event_ref"] == "cancel-1"
    assert package["revision"] == {"number": 1, "is_current": True, "supersedes_finding_id": None}
    assert package["net_potential"] == "40000"
    assert package["currency"] == "EUR"
    assert package["calculation"]["output_unit"] == "EUR"
    assert package["economic_truth_state"] == "DOCUMENTED_CANDIDATE_FOR_REVIEW"
    assert package["entitlement"]["confidence"] == "PARTIAL"
    assert package["entitlement"]["rule_ref"] == "documented-commercial-basis-v3-pre-review"
    assert package["entitlement"]["pre_review"] is True
    assert package["entitlement"]["generic_actionable"] is False
    assert package["entitlement"]["recoverability_established"] is False
    assert package["notice"] == {
        "truth_state": "DECLARED_DATE_FOR_REVIEW",
        "due_date": "2026-09-30",
        "timing_state": "OPEN",
        "as_of_date": "2026-09-29",
        "timing_establishes_recoverability": False,
        "expired_establishes_nonrecoverability": False,
        "expired_requires_human_exception_or_waiver_review": False,
    }
    assert package["finding"]["workflow_scope"] == "DOCUMENTARY_REVIEW"
    assert package["customer_action_authorized"] is False
    assert package["external_claim_submission_authorized"] is False
    assert package["legal_conclusion"] is None
    assert len(package["evidence_index"]) == 3
    assert all(item["content_hash"] for item in package["evidence_index"])
    assert {item["verification_state"] for item in package["evidence_index"]} == {"CONTENT_HASHED"}
    assert {item["raw_content_persisted"] for item in package["evidence_index"]} == {"false"}


def test_package_rejects_labels_that_do_not_match_immutable_recovery_identity(tmp_path):
    service, result = _package_result(tmp_path)

    for overrides in (
        {"customer_ref": "oem-2", "program_ref": "program-1", "event_ref": "cancel-1"},
        {"customer_ref": "oem-1", "program_ref": "program-2", "event_ref": "cancel-1"},
        {"customer_ref": "oem-1", "program_ref": "program-1", "event_ref": "other-event"},
    ):
        with pytest.raises(ValueError, match="labels do not match immutable case identity"):
            build_claim_package(service, result, **overrides, as_of_date=date(2026, 8, 29))


def test_package_rejects_hybrid_tenant_vertical_or_claim_family_identity(tmp_path):
    service, result = _package_result(tmp_path)
    labels = {"customer_ref": "oem-1", "program_ref": "program-1", "event_ref": "cancel-1", "as_of_date": date(2026, 8, 29)}

    wrong_tenant = replace(result, tenant_id="beta")
    with pytest.raises(ValueError, match="tenant identity does not match"):
        build_claim_package(service, wrong_tenant, **labels)

    wrong_vertical = replace(result, fingerprint=replace(result.fingerprint, vertical="contractcredit"))
    with pytest.raises(ValueError, match="fingerprint vertical is invalid"):
        build_claim_package(service, wrong_vertical, **labels)

    wrong_family = replace(result, claim_family="WIP")
    with pytest.raises(ValueError, match="claim family does not match"):
        build_claim_package(service, wrong_family, **labels)


def test_expired_declared_date_in_package_is_risk_not_nonrecoverability(tmp_path):
    service = IndustrialClaimsService(tmp_path / "expired-package.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="expired-1",
        claim_family="TOOLING", commercial_basis_ref="po-expired", cost_evidence_ref="invoice-expired", currency="EUR",
        gross_cost="50000", notice_due=date(2026, 9, 30), **_documents(),
    )
    package = build_claim_package(
        service, result,
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="expired-1",
        as_of_date=date(2026, 10, 1),
    )
    assert package["notice"]["timing_state"] == "EXPIRED"
    assert package["notice"]["expired_requires_human_exception_or_waiver_review"] is True
    assert package["notice"]["expired_establishes_nonrecoverability"] is False
    assert package["notice"]["timing_establishes_recoverability"] is False
    assert package["economic_truth_state"] == "DOCUMENTED_CANDIDATE_FOR_REVIEW"


def test_missing_evidence_package_stays_potential_entitlement(tmp_path):
    service = IndustrialClaimsService(tmp_path / "industrial.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="reduction-1",
        claim_family="FINISHED_GOODS", commercial_basis_ref="contract-1", cost_evidence_ref="inventory-1", currency="EUR",
        gross_cost="75000", missing_evidence=("ownership", "release_history"), **_documents(),
    )
    package = build_claim_package(
        service, result,
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="reduction-1",
        as_of_date=date(2026, 8, 29),
    )
    assert package["economic_truth_state"] == "POTENTIAL_ENTITLEMENT"
    assert package["currency"] == "EUR"
    assert package["entitlement"]["confidence"] == "UNRESOLVED"
    assert package["entitlement"]["pre_review"] is True
    assert package["entitlement"]["generic_actionable"] is False
    assert package["entitlement"]["recoverability_established"] is False
    assert package["notice"]["truth_state"] == "UNKNOWN"
    assert package["notice"]["due_date"] is None
    assert package["notice"]["timing_state"] == "UNKNOWN"
    assert package["missing_evidence"] == [NOTICE_DEADLINE_EVIDENCE, "ownership", "release_history"]
    assert {item["verification_state"] for item in package["evidence_index"]} == {"CONTENT_HASHED"}


def test_reference_only_package_cannot_claim_evidence_supported(tmp_path):
    service = IndustrialClaimsService(tmp_path / "reference-only.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="reference-only",
        claim_family="TOOLING", commercial_basis_ref="po-reference", cost_evidence_ref="ledger-reference", currency="EUR",
        gross_cost="10000", notice_deadline_not_applicable=True,
    )
    package = build_claim_package(
        service, result,
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="reference-only",
        as_of_date=date(2026, 8, 29),
    )
    assert package["economic_truth_state"] == "POTENTIAL_ENTITLEMENT"
    assert package["currency"] == "EUR"
    assert package["entitlement"]["confidence"] == "UNRESOLVED"
    assert package["entitlement"]["generic_actionable"] is False
    assert package["entitlement"]["recoverability_established"] is False
    assert package["notice"]["timing_state"] == "NO_DEADLINE_DECLARED_FOR_REVIEW"
    assert {item["verification_state"] for item in package["evidence_index"]} == {"REFERENCE_ONLY"}
    assert package["customer_action_authorized"] is False
    assert package["external_claim_submission_authorized"] is False
    assert package["legal_conclusion"] is None


def test_missing_currency_is_never_fabricated_in_package(tmp_path):
    service = IndustrialClaimsService(tmp_path / "missing-currency.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="no-currency",
        claim_family="WIP", commercial_basis_ref="po-no-currency", cost_evidence_ref="ledger-no-currency",
        gross_cost="10000", notice_deadline_not_applicable=True, **_documents(),
    )
    package = build_claim_package(
        service, result,
        customer_ref="oem-1",
        program_ref="program-1",
        event_ref="no-currency",
        as_of_date=date(2026, 8, 29),
    )
    assert package["currency"] is None
    assert package["calculation"]["output_unit"] == "UNKNOWN"
    assert CLAIM_CURRENCY_EVIDENCE in package["missing_evidence"]
    assert package["entitlement"]["confidence"] == "UNRESOLVED"
    assert package["entitlement"]["generic_actionable"] is False
    assert package["economic_truth_state"] == "POTENTIAL_ENTITLEMENT"


def test_package_rejects_superseded_result_and_exports_current_revision(tmp_path):
    service = IndustrialClaimsService(tmp_path / "package-revision.sqlite3")
    first = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="amend-1",
        claim_family="TOOLING", commercial_basis_ref="po-1", cost_evidence_ref="invoice-1", currency="EUR",
        gross_cost="50000", notice_deadline_not_applicable=True, **_documents(),
    )
    second = amend_case(
        service, tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="analyst-2",
        customer_ref="oem-1", program_ref="program-1", event_ref="amend-1", claim_family="TOOLING",
        commercial_basis_ref="po-1", cost_evidence_ref="invoice-2", gross_cost="52000", currency="EUR",
        commercial_basis_content="signed supply agreement and purchase order terms",
        event_evidence_content="documented cancellation or reduction event",
        cost_evidence_content="corrected invoice and cost ledger supporting the exposure",
        notice_deadline_not_applicable=True,
    )
    labels = {"customer_ref": "oem-1", "program_ref": "program-1", "event_ref": "amend-1", "as_of_date": date(2026, 8, 30)}

    with pytest.raises(ValueError, match="requires the current non-superseded"):
        build_claim_package(service, first, **labels)

    package = build_claim_package(service, second, **labels)
    assert package["revision"] == {
        "number": 2,
        "is_current": True,
        "supersedes_finding_id": first.finding.finding_id,
    }
    assert package["finding"]["finding_id"] == second.finding.finding_id
    assert package["net_potential"] == "52000"
