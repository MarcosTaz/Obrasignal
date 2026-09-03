from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from typing import Any

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.service import IndustrialClaimResult, IndustrialClaimsService


def _notice_package(result: IndustrialClaimResult, *, as_of_date: date) -> dict[str, Any]:
    if result.notice_deadline_state == "DECLARED_DATE_FOR_REVIEW":
        timing_state = result.deadline.state_on(as_of_date)
        due_date = result.deadline.due_date.isoformat()
    elif result.notice_deadline_state == "DECLARED_NONE_FOR_REVIEW":
        timing_state = "NO_DEADLINE_DECLARED_FOR_REVIEW"
        due_date = None
    else:
        timing_state = "UNKNOWN"
        due_date = None
    return {
        "truth_state": result.notice_deadline_state,
        "due_date": due_date,
        "timing_state": timing_state,
        "as_of_date": as_of_date.isoformat(),
        "timing_establishes_recoverability": False,
        "expired_establishes_nonrecoverability": False,
        "expired_requires_human_exception_or_waiver_review": timing_state == "EXPIRED",
    }


def _immutable_case_labels(result: IndustrialClaimResult) -> tuple[str, str, str]:
    fingerprint = result.fingerprint
    if fingerprint.tenant_id != result.tenant_id:
        raise ValueError("industrial package tenant identity does not match recovery fingerprint")
    if fingerprint.vertical != "industrial-claims":
        raise ValueError("industrial package recovery fingerprint vertical is invalid")
    if fingerprint.remedy_type != result.claim_family.lower():
        raise ValueError("industrial package claim family does not match recovery fingerprint")
    try:
        contract_parts = json.loads(fingerprint.contract_ref)
    except (TypeError, ValueError) as exc:
        raise ValueError("industrial package contract identity is invalid") from exc
    if not isinstance(contract_parts, list) or len(contract_parts) != 3:
        raise ValueError("industrial package contract identity is invalid")
    customer_ref, program_ref, _commercial_basis_ref = (str(value) for value in contract_parts)
    event_ref = str(fingerprint.event_ref)
    if not customer_ref or not program_ref or not event_ref:
        raise ValueError("industrial package case identity is incomplete")
    return customer_ref, program_ref, event_ref


def _current_revision(service: IndustrialClaimsService, result: IndustrialClaimResult):
    try:
        revision = service.revision_store.require_current(
            tenant_id=result.tenant_id,
            finding_id=result.finding.finding_id,
        )
    except AssuranceStoreError as exc:
        raise ValueError("industrial package requires the current non-superseded finding revision") from exc
    if revision.recovery_fingerprint != result.fingerprint.fingerprint:
        raise ValueError("industrial package revision fingerprint does not match result")
    return revision


def _verify_durable_snapshot(service: IndustrialClaimsService, result: IndustrialClaimResult) -> None:
    try:
        detail = service.read_model.get_finding(
            tenant_id=result.tenant_id,
            finding_id=result.finding.finding_id,
        )
    except AssuranceStoreError as exc:
        raise ValueError("industrial package durable dossier validation failed") from exc

    case = detail["case"]
    finding = detail["finding"]
    calculation = detail["calculation"]
    entitlement = detail["entitlement"]
    if case["recovery_fingerprint"] != result.fingerprint.fingerprint:
        raise ValueError("industrial package durable recovery fingerprint does not match result")
    if case["claim_family"] != result.claim_family:
        raise ValueError("industrial package durable claim family does not match result")
    if tuple(case["missing_evidence"]) != tuple(result.missing_evidence):
        raise ValueError("industrial package durable missing-evidence state does not match result")
    if case["notice_deadline_state"] != result.notice_deadline_state:
        raise ValueError("industrial package durable notice truth does not match result")
    if finding["state"] != result.finding.state:
        raise ValueError("industrial package result lifecycle state is stale relative to durable dossier")
    if (
        calculation["formula_id"] != result.calculation.formula_id
        or calculation["formula_version"] != result.calculation.formula_version
        or calculation["net_potential"] != result.calculation.output_value
        or calculation["currency"] != result.calculation.output_unit
        or calculation["reproducibility_hash"] != result.calculation.reproducibility_hash
    ):
        raise ValueError("industrial package durable calculation does not match result")
    if (
        entitlement["rule_ref"] != result.entitlement.rule_ref
        or entitlement["confidence"] != result.entitlement.confidence
        or entitlement["basis_hash"] != result.entitlement.basis_hash
    ):
        raise ValueError("industrial package durable entitlement does not match result")

    durable_evidence = {
        item["evidence_id"]: (
            item["source_type"],
            item["source_ref"],
            item["content_hash"],
            item["verification_state"],
        )
        for item in detail["evidence_index"]
    }
    result_evidence = {
        item.evidence_id: (
            item.source_type,
            item.source_ref,
            item.content_hash,
            item.metadata.get("verification_state", "UNKNOWN"),
        )
        for item in result.evidence
    }
    if durable_evidence != result_evidence:
        raise ValueError("industrial package durable evidence index does not match result")


def build_claim_package(
    service: IndustrialClaimsService,
    result: IndustrialClaimResult,
    *,
    customer_ref: str,
    program_ref: str,
    event_ref: str,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """Build a current durable review package without upgrading legal truth.

    The revision store and read model are authoritative for export currentness
    and lifecycle/economic/evidence truth. A stale in-memory result is rejected
    instead of being rendered as though it still matched the durable dossier.
    """
    immutable_customer, immutable_program, immutable_event = _immutable_case_labels(result)
    revision = _current_revision(service, result)
    _verify_durable_snapshot(service, result)
    supplied = (str(customer_ref), str(program_ref), str(event_ref))
    immutable = (immutable_customer, immutable_program, immutable_event)
    if supplied != immutable:
        raise ValueError("industrial package labels do not match immutable case identity")

    as_of = as_of_date or date.today()
    currency = result.calculation.output_unit
    verified_currency = currency if currency and currency != "UNKNOWN" else None
    return {
        "schema_version": 7,
        "vertical": "industrial-claims",
        "tenant_id": result.tenant_id,
        "customer_ref": immutable_customer,
        "program_ref": immutable_program,
        "event_ref": immutable_event,
        "claim_family": result.claim_family,
        "revision": {
            "number": revision.revision,
            "is_current": True,
            "supersedes_finding_id": revision.supersedes_finding_id,
        },
        "economic_truth_state": "DOCUMENTED_CANDIDATE_FOR_REVIEW" if result.finding.state == "READY_FOR_REVIEW" else "POTENTIAL_ENTITLEMENT",
        "net_potential": result.calculation.output_value,
        "currency": verified_currency,
        "calculation": {
            "formula_id": result.calculation.formula_id,
            "formula_version": result.calculation.formula_version,
            "reproducibility_hash": result.calculation.reproducibility_hash,
            "output_unit": result.calculation.output_unit,
            "inputs": [asdict(item) for item in result.calculation.inputs],
        },
        "entitlement": {
            "rule_ref": result.entitlement.rule_ref,
            "confidence": result.entitlement.confidence,
            "basis_hash": result.entitlement.basis_hash,
            "pre_review": True,
            "generic_actionable": False,
            "recoverability_established": False,
        },
        "notice": _notice_package(result, as_of_date=as_of),
        "evidence_index": [
            {
                "evidence_id": item.evidence_id,
                "source_type": item.source_type,
                "source_ref": item.source_ref,
                "content_hash": item.content_hash,
                "verification_state": item.metadata.get("verification_state", "UNKNOWN"),
                "raw_content_persisted": item.metadata.get("raw_content_persisted", "unknown"),
            }
            for item in result.evidence
        ],
        "missing_evidence": list(result.missing_evidence),
        "finding": {
            "finding_id": result.finding.finding_id,
            "state": result.finding.state,
            "workflow_scope": "DOCUMENTARY_REVIEW",
        },
        "duplicate_status": "NEW" if result.is_new_recovery else "REPLAY_OR_DUPLICATE",
        "customer_action_authorized": False,
        "external_claim_submission_authorized": False,
        "legal_conclusion": None,
    }
