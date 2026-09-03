import json
from pathlib import Path

import pytest

from vertical_apps.industrial_claims.amendment import amend_case
from vertical_apps.industrial_claims.dossier import AssistedRecoveryAssessment, build_assisted_dossier, render_dossier_markdown
from vertical_apps.industrial_claims.service import IndustrialClaimsService


FIXTURE = Path("vertical_apps/industrial_claims/fixtures/nre_adversarial_cases.json")


def _assessment(case):
    return AssistedRecoveryAssessment(
        reviewer="commercial-reviewer",
        contract_change_truth=f"Reviewed commercial basis for {case['id']}; only documentary support is represented.",
        event_chronology=f"Reviewed customer/change chronology for {case['id']}.",
        causation_state=case["causation"],
        causation_summary=f"Causation assessment for {case['id']}: {case['scenario']}",
        customer_responsibility_state=case["responsibility"],
        customer_responsibility_summary=f"Responsibility assessment for {case['id']} remains bounded by contract/PO/change evidence.",
        prior_recovery_state=case["prior_recovery"],
        prior_recovery_summary=f"Prior recovery reconciliation state for {case['id']}: {case['prior_recovery']}.",
        confidence=case["confidence"],
        next_action="Request missing evidence or proceed to independent review according to disposition.",
    )


def test_24_adversarial_nre_cases_produce_fail_closed_assisted_dossier_dispositions(tmp_path):
    cases = json.loads(FIXTURE.read_text())
    assert len(cases) >= 24
    assert {case["id"] for case in cases} == {f"NRE-{number:02d}" for number in range(1, 25)}

    service = IndustrialClaimsService(tmp_path / "nre-adversarial.sqlite3")
    dispositions = set()
    for index, case in enumerate(cases, start=1):
        result = service.analyze(
            tenant_id="alpha",
            actor_id=f"analyst-{index}",
            customer_ref=f"customer-{index}",
            program_ref=f"program-{index}",
            event_ref=f"change-{index}",
            claim_family="NRE",
            commercial_basis_ref=f"po-{index}",
            cost_evidence_ref=f"ledger-{index}",
            gross_cost="10000",
            currency="EUR",
            commercial_basis_content=f"bounded commercial terms for {case['id']}",
            event_evidence_content=f"bounded change/event evidence for {case['id']}",
            cost_evidence_content=f"bounded incremental engineering cost evidence for {case['id']}",
            notice_deadline_not_applicable=True,
            missing_evidence=tuple(case["missing_evidence"]),
        )
        dossier = build_assisted_dossier(
            service,
            tenant_id="alpha",
            finding_id=result.finding.finding_id,
            assessment=_assessment(case),
        )
        assert dossier["executive_case_sheet"]["disposition"] == case["expected"]
        assert dossier["case"]["claim_family"] == "NRE"
        assert dossier["customer_action_authorized"] is False
        assert dossier["external_claim_submission_authorized"] is False
        assert dossier["recoverability_established"] is False
        assert dossier["raw_document_content_included"] is False
        dispositions.add(dossier["executive_case_sheet"]["disposition"])

    assert "DOCUMENTED_CANDIDATE_FOR_INDEPENDENT_REVIEW" in dispositions
    assert "NEEDS_REVIEW_OR_DOCUMENTS" in dispositions
    assert "NO_CLAIM_ALREADY_RECOVERED" in dispositions


def test_assisted_dossier_rejects_superseded_revision(tmp_path):
    service = IndustrialClaimsService(tmp_path / "dossier-revision.sqlite3")
    first = service.analyze(
        tenant_id="alpha", actor_id="analyst-1", customer_ref="oem", program_ref="program", event_ref="ecn-1",
        claim_family="NRE", commercial_basis_ref="po-1", cost_evidence_ref="ledger-1", gross_cost="10000", currency="EUR",
        commercial_basis_content="signed change reimbursement terms", event_evidence_content="signed customer ECN",
        cost_evidence_content="engineering ledger", notice_deadline_not_applicable=True,
    )
    second = amend_case(
        service, tenant_id="alpha", finding_id=first.finding.finding_id, actor_id="analyst-2",
        customer_ref="oem", program_ref="program", event_ref="ecn-1", claim_family="NRE",
        commercial_basis_ref="po-1", cost_evidence_ref="ledger-2", gross_cost="12000", currency="EUR",
        commercial_basis_content="signed change reimbursement terms", event_evidence_content="signed customer ECN",
        cost_evidence_content="corrected engineering ledger", notice_deadline_not_applicable=True,
    )
    assessment = AssistedRecoveryAssessment(
        reviewer="commercial-reviewer", contract_change_truth="Signed ECN and PO terms reviewed.",
        event_chronology="Customer ECN preceded incremental engineering work.", causation_state="SUPPORTED",
        causation_summary="Incremental work follows the documented ECN.", customer_responsibility_state="SUPPORTED",
        customer_responsibility_summary="Commercial terms support reimbursement review; no legal conclusion is asserted.",
        prior_recovery_state="VERIFIED_NONE", prior_recovery_summary="No prior credit/payment found in reviewed evidence.",
        confidence="HIGH", next_action="Independent reviewer to decide internal workflow approval.",
    )

    with pytest.raises(ValueError, match="current durable finding"):
        build_assisted_dossier(service, tenant_id="alpha", finding_id=first.finding.finding_id, assessment=assessment)
    assert build_assisted_dossier(
        service, tenant_id="alpha", finding_id=second.finding.finding_id, assessment=assessment
    )["case"]["revision"]["number"] == 2


def test_markdown_renderer_is_customer_reviewable_and_never_embeds_raw_documents(tmp_path):
    service = IndustrialClaimsService(tmp_path / "markdown-dossier.sqlite3")
    result = service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem", program_ref="program", event_ref="ecn-2",
        claim_family="NRE", commercial_basis_ref="po-2", cost_evidence_ref="ledger-2", gross_cost="15000", currency="EUR",
        commercial_basis_content="SECRET RAW PO CONTENT", event_evidence_content="SECRET RAW CHANGE CONTENT",
        cost_evidence_content="SECRET RAW LEDGER CONTENT", notice_deadline_not_applicable=True,
    )
    case = {
        "id": "NRE-RENDER",
        "scenario": "signed customer change with traceable incremental engineering cost",
        "missing_evidence": [],
        "causation": "SUPPORTED",
        "responsibility": "SUPPORTED",
        "prior_recovery": "VERIFIED_NONE",
        "confidence": "HIGH",
    }
    dossier = build_assisted_dossier(
        service, tenant_id="alpha", finding_id=result.finding.finding_id, assessment=_assessment(case)
    )
    markdown = render_dossier_markdown(dossier)

    assert "# CausLedger — Assisted Recovery Dossier" in markdown
    assert "## Documentary index" in markdown
    assert "## Contract / PO / change truth" in markdown
    assert "## Causation assessment" in markdown
    assert "## Customer responsibility assessment" in markdown
    assert "## Cost reconstruction" in markdown
    assert "## Prior recovery check" in markdown
    assert "## Notice / deadline" in markdown
    assert "## Evidence gaps / attack list" in markdown
    assert "Candidate value is not automatically money owed" in markdown
    assert "SECRET RAW PO CONTENT" not in markdown
    assert "SECRET RAW CHANGE CONTENT" not in markdown
    assert "SECRET RAW LEDGER CONTENT" not in markdown
    assert "External claim submission authorized: False" in markdown
