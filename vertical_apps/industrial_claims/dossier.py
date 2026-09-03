from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.service import IndustrialClaimsService


ASSESSMENT_STATES = {"SUPPORTED", "PARTIAL", "UNRESOLVED", "CONTRADICTED"}
PRIOR_RECOVERY_STATES = {"VERIFIED_NONE", "VERIFIED_PARTIAL", "VERIFIED_FULL", "UNKNOWN"}
CONFIDENCE_STATES = {"HIGH", "MEDIUM", "LOW", "UNRESOLVED"}
MAX_SUMMARY_CHARS = 4_000
MAX_NEXT_ACTION_CHARS = 2_000


@dataclass(frozen=True)
class AssistedRecoveryAssessment:
    reviewer: str
    contract_change_truth: str
    event_chronology: str
    causation_state: str
    causation_summary: str
    customer_responsibility_state: str
    customer_responsibility_summary: str
    prior_recovery_state: str
    prior_recovery_summary: str
    confidence: str
    next_action: str


def _text(value: object, *, label: str, max_chars: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    if len(text) > max_chars:
        raise ValueError(f"{label} exceeds {max_chars} characters")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text) or any(ord(char) == 127 for char in text):
        raise ValueError(f"{label} contains forbidden control characters")
    return text


def _choice(value: object, *, label: str, allowed: set[str]) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in allowed:
        raise ValueError(f"{label} is invalid")
    return normalized


def _validated(assessment: AssistedRecoveryAssessment) -> AssistedRecoveryAssessment:
    return AssistedRecoveryAssessment(
        reviewer=_text(assessment.reviewer, label="reviewer", max_chars=256),
        contract_change_truth=_text(assessment.contract_change_truth, label="contract/change truth", max_chars=MAX_SUMMARY_CHARS),
        event_chronology=_text(assessment.event_chronology, label="event chronology", max_chars=MAX_SUMMARY_CHARS),
        causation_state=_choice(assessment.causation_state, label="causation state", allowed=ASSESSMENT_STATES),
        causation_summary=_text(assessment.causation_summary, label="causation summary", max_chars=MAX_SUMMARY_CHARS),
        customer_responsibility_state=_choice(
            assessment.customer_responsibility_state,
            label="customer responsibility state",
            allowed=ASSESSMENT_STATES,
        ),
        customer_responsibility_summary=_text(
            assessment.customer_responsibility_summary,
            label="customer responsibility summary",
            max_chars=MAX_SUMMARY_CHARS,
        ),
        prior_recovery_state=_choice(
            assessment.prior_recovery_state,
            label="prior recovery state",
            allowed=PRIOR_RECOVERY_STATES,
        ),
        prior_recovery_summary=_text(
            assessment.prior_recovery_summary,
            label="prior recovery summary",
            max_chars=MAX_SUMMARY_CHARS,
        ),
        confidence=_choice(assessment.confidence, label="confidence", allowed=CONFIDENCE_STATES),
        next_action=_text(assessment.next_action, label="next action", max_chars=MAX_NEXT_ACTION_CHARS),
    )


def _disposition(*, detail: dict[str, Any], assessment: AssistedRecoveryAssessment) -> str:
    state = str(detail["finding"]["state"])
    if state == "REJECTED":
        return "NO_CLAIM_OR_REJECTED"
    if assessment.prior_recovery_state == "VERIFIED_FULL":
        return "NO_CLAIM_ALREADY_RECOVERED"
    if (
        detail["case"]["missing_evidence"]
        or assessment.causation_state != "SUPPORTED"
        or assessment.customer_responsibility_state != "SUPPORTED"
        or assessment.prior_recovery_state == "UNKNOWN"
        or assessment.confidence in {"LOW", "UNRESOLVED"}
    ):
        return "NEEDS_REVIEW_OR_DOCUMENTS"
    if state == "READY_FOR_REVIEW":
        return "DOCUMENTED_CANDIDATE_FOR_INDEPENDENT_REVIEW"
    if state == "APPROVED":
        return "INTERNALLY_APPROVED_FOR_WORKFLOW"
    if state == "ACTIONED":
        return "ACTIONED_INTERNALLY"
    if state in {"RECOVERED", "CLOSED_NO_RECOVERY"}:
        return "DOCUMENTED_FINAL_OUTCOME"
    return "NEEDS_REVIEW_OR_DOCUMENTS"


def build_assisted_dossier(
    service: IndustrialClaimsService,
    *,
    tenant_id: str,
    finding_id: str,
    assessment: AssistedRecoveryAssessment,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """Build the paid-delivery dossier from durable case truth plus human assessment.

    This function never upgrades customer responsibility or legal recoverability
    from cost alone. Human causation/responsibility assessments remain explicitly
    labelled assessments and external action remains unauthorized by default.
    """
    reviewed = _validated(assessment)
    try:
        detail = service.read_model.get_finding(
            tenant_id=tenant_id,
            finding_id=finding_id,
            as_of_date=as_of_date,
        )
        service.revision_store.require_current(tenant_id=tenant_id, finding_id=finding_id)
    except AssuranceStoreError as exc:
        raise ValueError("assisted dossier requires a valid current durable finding") from exc

    disposition = _disposition(detail=detail, assessment=reviewed)
    calculation = detail["calculation"]
    return {
        "schema_version": 1,
        "deliverable": "CAUSLEDGER_ASSISTED_RECOVERY_DOSSIER",
        "case": {
            **detail["case"],
            "revision": detail["revision"],
            "workflow_state": detail["finding"]["state"],
        },
        "executive_case_sheet": {
            "net_potential": calculation["net_potential"],
            "currency": calculation["currency"],
            "confidence": reviewed.confidence,
            "disposition": disposition,
            "notice_timing_state": detail["notice"]["timing_state"],
            "next_action": reviewed.next_action,
            "candidate_value_is_money_owed": False,
        },
        "documentary_index": detail["evidence_index"],
        "contract_po_change_truth": reviewed.contract_change_truth,
        "event_chronology": reviewed.event_chronology,
        "causation": {
            "state": reviewed.causation_state,
            "summary": reviewed.causation_summary,
        },
        "customer_responsibility": {
            "state": reviewed.customer_responsibility_state,
            "summary": reviewed.customer_responsibility_summary,
            "legal_conclusion": None,
        },
        "cost_reconstruction": calculation,
        "prior_recovery_check": {
            "state": reviewed.prior_recovery_state,
            "summary": reviewed.prior_recovery_summary,
        },
        "notice_deadline": detail["notice"],
        "evidence_gaps": list(detail["case"]["missing_evidence"]),
        "review": {
            "reviewer": reviewed.reviewer,
            "confidence": reviewed.confidence,
            "human_assessment_required": True,
        },
        "outcomes": detail["outcomes"],
        "next_action": reviewed.next_action,
        "customer_action_authorized": False,
        "external_claim_submission_authorized": False,
        "recoverability_established": False,
        "raw_document_content_included": False,
    }


def _md(value: object) -> str:
    return str(value if value is not None else "UNKNOWN").replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def render_dossier_markdown(dossier: dict[str, Any]) -> str:
    """Render a customer-reviewable Markdown dossier without embedding raw evidence."""
    if dossier.get("deliverable") != "CAUSLEDGER_ASSISTED_RECOVERY_DOSSIER":
        raise ValueError("unsupported dossier deliverable")
    if dossier.get("raw_document_content_included") is not False:
        raise ValueError("dossier rendering refuses raw document content")

    case = dossier["case"]
    sheet = dossier["executive_case_sheet"]
    causation = dossier["causation"]
    responsibility = dossier["customer_responsibility"]
    prior = dossier["prior_recovery_check"]
    notice = dossier["notice_deadline"]
    calc = dossier["cost_reconstruction"]
    gaps = dossier["evidence_gaps"]

    evidence_rows = [
        f"| {_md(item.get('source_type'))} | {_md(item.get('source_ref'))} | `{_md(item.get('content_hash'))}` | {_md(item.get('verification_state'))} |"
        for item in dossier["documentary_index"]
    ]
    gap_lines = [f"- {_md(item)}" for item in gaps] or ["- None recorded in the durable case metadata."]
    outcome_lines = [
        f"- {_md(item.get('state'))}: {_md(item.get('recovered_amount'))} {_md(item.get('currency'))} — evidence ref {_md(item.get('evidence', {}).get('source_ref'))}"
        for item in dossier.get("outcomes", [])
    ] or ["- No documented final outcome recorded."]

    return "\n".join([
        "# CausLedger — Assisted Recovery Dossier",
        "",
        "> Evidence-first commercial review. Candidate value is not automatically money owed and this dossier is not a legal conclusion.",
        "",
        "## Executive case sheet",
        f"- Finding: `{_md(case.get('finding_id'))}`",
        f"- Revision: {_md(case.get('revision', {}).get('number'))} (current: {_md(case.get('revision', {}).get('is_current'))})",
        f"- Customer / program / event: {_md(case.get('customer_ref'))} / {_md(case.get('program_ref'))} / {_md(case.get('event_ref'))}",
        f"- Claim family: {_md(case.get('claim_family'))}",
        f"- Workflow state: {_md(case.get('workflow_state'))}",
        f"- Net potential: {_md(sheet.get('net_potential'))} {_md(sheet.get('currency'))}",
        f"- Confidence: {_md(sheet.get('confidence'))}",
        f"- Disposition: **{_md(sheet.get('disposition'))}**",
        f"- Notice timing: {_md(sheet.get('notice_timing_state'))}",
        f"- Next action: {_md(sheet.get('next_action'))}",
        "",
        "## Documentary index",
        "| Type | Source reference | Content hash | Provenance state |",
        "| --- | --- | --- | --- |",
        *evidence_rows,
        "",
        "## Contract / PO / change truth",
        _md(dossier["contract_po_change_truth"]),
        "",
        "## Event chronology",
        _md(dossier["event_chronology"]),
        "",
        "## Causation assessment",
        f"**State:** {_md(causation.get('state'))}",
        "",
        _md(causation.get("summary")),
        "",
        "## Customer responsibility assessment",
        f"**State:** {_md(responsibility.get('state'))}",
        "",
        _md(responsibility.get("summary")),
        "",
        "**Legal conclusion:** none asserted by this dossier.",
        "",
        "## Cost reconstruction",
        f"- Formula: {_md(calc.get('formula_id'))} v{_md(calc.get('formula_version'))}",
        f"- Net potential: {_md(calc.get('net_potential'))} {_md(calc.get('currency'))}",
        f"- Reproducibility hash: `{_md(calc.get('reproducibility_hash'))}`",
        "",
        "## Prior recovery check",
        f"**State:** {_md(prior.get('state'))}",
        "",
        _md(prior.get("summary")),
        "",
        "## Notice / deadline",
        f"- Truth state: {_md(notice.get('truth_state'))}",
        f"- Due date: {_md(notice.get('due_date'))}",
        f"- Timing state: {_md(notice.get('timing_state'))}",
        f"- Expiry establishes non-recoverability: {_md(notice.get('expired_establishes_nonrecoverability'))}",
        "",
        "## Evidence gaps / attack list",
        *gap_lines,
        "",
        "## Documented outcome",
        *outcome_lines,
        "",
        "## Release controls",
        f"- Reviewer: {_md(dossier.get('review', {}).get('reviewer'))}",
        f"- Customer action authorized: {_md(dossier.get('customer_action_authorized'))}",
        f"- External claim submission authorized: {_md(dossier.get('external_claim_submission_authorized'))}",
        f"- Recoverability established by software: {_md(dossier.get('recoverability_established'))}",
        f"- Raw document content included: {_md(dossier.get('raw_document_content_included'))}",
        "",
        "## Next action",
        _md(dossier["next_action"]),
        "",
    ])
