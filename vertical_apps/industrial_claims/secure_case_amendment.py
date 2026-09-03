from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
from typing import TYPE_CHECKING, Mapping

from factory_cloud.assurance_kernel import (
    CalculationInput,
    CalculationRecord,
    DeadlineWindow,
    FindingRecord,
    assert_same_tenant,
)
from factory_cloud.assurance_ops import AssuranceOperationError
from factory_cloud.assurance_store import AssuranceStoreError
from factory_cloud.recovery_primitives import EntitlementBasis, RecoveryFingerprint
from factory_cloud.shared_platform import AuditEvent, NotificationEvent, TenantContext, assert_tenant_context
from vertical_apps.industrial_claims.amendment import AMENDABLE_STATES, _current_source_ref
from vertical_apps.industrial_claims.case_store import IndustrialCaseMetadata
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry
from vertical_apps.industrial_claims.secure_case_intake import _load_case_evidence

if TYPE_CHECKING:
    from vertical_apps.industrial_claims.service import IndustrialClaimResult, IndustrialClaimsService


class SecureCaseAmendmentError(RuntimeError):
    pass


def amend_case_from_secure_capture(
    service: "IndustrialClaimsService",
    registry: SecureCaptureRegistry,
    *,
    tenant_id: str,
    finding_id: str,
    actor_id: str,
    intake_case_ref: str,
    evidence_ids: Mapping[str, str],
    customer_ref: str,
    program_ref: str,
    event_ref: str,
    claim_family: str,
    commercial_basis_ref: str,
    cost_evidence_ref: str,
    gross_cost: str,
    currency: str,
    avoided_cost: str = "0",
    resale_reuse: str = "0",
    third_party_recovery: str = "0",
    prior_payment: str = "0",
    other_mitigation: str = "0",
    notice_due: date | None = None,
    notice_deadline_not_applicable: bool = False,
    missing_evidence: tuple[str, ...] = (),
) -> "IndustrialClaimResult":
    """Supersede a current case revision using exact authorized immutable originals.

    No raw bytes or external provider calls are accepted here. The new revision is
    built from already-registered secure-capture envelopes, preserves the recovery
    fingerprint identity, and always requires fresh independent review.
    """
    from vertical_apps.industrial_claims.service import (
        CLAIM_CURRENCY_EVIDENCE,
        DECIMAL_WORKING_PRECISION,
        MAX_ACTOR_CHARS,
        MAX_FINDING_ID_CHARS,
        MAX_REFERENCE_CHARS,
        NOTICE_DEADLINE_EVIDENCE,
        IndustrialClaimResult,
    )

    tenant = service._operation_tenant_id(tenant_id)
    finding_key = service._bounded_operation_text(
        finding_id,
        label="finding_id",
        max_chars=MAX_FINDING_ID_CHARS,
    )
    actor = service._bounded_operation_text(
        actor_id,
        label="amendment actor",
        max_chars=MAX_ACTOR_CHARS,
    )
    intake_ref = service._bounded_operation_text(
        intake_case_ref,
        label="intake_case_ref",
        max_chars=MAX_REFERENCE_CHARS,
    )
    service._assert_dossier_integrity(tenant_id=tenant, finding_id=finding_key)
    current_revision = service.revision_store.require_current(
        tenant_id=tenant,
        finding_id=finding_key,
    )
    metadata = service.case_store.get(tenant_id=tenant, finding_id=finding_key)
    detail = service.read_model.get_finding(tenant_id=tenant, finding_id=finding_key)

    customer = service._bounded_text(customer_ref, label="customer_ref", max_chars=MAX_REFERENCE_CHARS)
    program = service._bounded_text(program_ref, label="program_ref", max_chars=MAX_REFERENCE_CHARS)
    event_key = service._bounded_text(event_ref, label="event_ref", max_chars=MAX_REFERENCE_CHARS)
    basis_ref = service._bounded_text(
        commercial_basis_ref,
        label="commercial_basis_ref",
        max_chars=MAX_REFERENCE_CHARS,
    )
    cost_ref = service._bounded_text(
        cost_evidence_ref,
        label="cost_evidence_ref",
        max_chars=MAX_REFERENCE_CHARS,
    )
    family = str(claim_family or "").strip().upper()

    current_basis_ref = _current_source_ref(detail, "commercial_basis")
    immutable_supplied = (customer, program, event_key, family, basis_ref)
    immutable_current = (
        metadata.customer_ref,
        metadata.program_ref,
        metadata.event_ref,
        metadata.claim_family,
        current_basis_ref,
    )
    if immutable_supplied != immutable_current:
        raise AssuranceOperationError("amendment cannot change recovery fingerprint identity fields")

    fingerprint = RecoveryFingerprint.create(
        tenant_id=tenant,
        vertical=service.vertical,
        contract_ref=service._contract_ref(customer, program, basis_ref),
        event_ref=event_key,
        remedy_type=family.lower(),
    )
    if (
        fingerprint.fingerprint != metadata.recovery_fingerprint
        or fingerprint.fingerprint != current_revision.recovery_fingerprint
    ):
        raise AssuranceStoreError("industrial amendment fingerprint does not match current case")

    if not isinstance(notice_deadline_not_applicable, bool):
        raise AssuranceOperationError("notice_deadline_not_applicable must be boolean")
    if notice_due is not None and notice_deadline_not_applicable:
        raise AssuranceOperationError("notice due date and declared no-deadline state are mutually exclusive")

    evidence, authorization_id, authorization_scope_sha256 = _load_case_evidence(
        registry,
        tenant_id=tenant,
        intake_case_ref=intake_ref,
        evidence_ids=evidence_ids,
        source_refs={
            "commercial_basis": basis_ref,
            "event": event_key,
            "cost": cost_ref,
        },
    )
    basis, event, cost = evidence

    effective_missing = service._bounded_missing_evidence(missing_evidence)
    currency_code = service._claim_currency(currency)
    if not currency_code:
        currency_code = "UNKNOWN"
        effective_missing.add(CLAIM_CURRENCY_EVIDENCE)
    if notice_due is not None:
        notice_deadline_state = "DECLARED_DATE_FOR_REVIEW"
    elif notice_deadline_not_applicable:
        notice_deadline_state = "DECLARED_NONE_FOR_REVIEW"
    else:
        notice_deadline_state = "UNKNOWN"
        effective_missing.add(NOTICE_DEADLINE_EVIDENCE)

    amounts = {
        "gross_cost": service._claim_amount(gross_cost),
        "avoided_cost": service._claim_amount(avoided_cost),
        "resale_reuse": service._claim_amount(resale_reuse),
        "third_party_recovery": service._claim_amount(third_party_recovery),
        "prior_payment": service._claim_amount(prior_payment),
        "other_mitigation": service._claim_amount(other_mitigation),
    }
    if any(value < 0 for value in amounts.values()):
        raise AssuranceOperationError("industrial claim amounts cannot be negative")
    with localcontext() as decimal_context:
        decimal_context.prec = DECIMAL_WORKING_PRECISION
        deductions = sum(
            (value for key, value in amounts.items() if key != "gross_cost"),
            Decimal("0"),
        )
        net_potential = amounts["gross_cost"] - deductions
    if net_potential < 0:
        raise AssuranceOperationError("mitigation/recovery cannot exceed gross cost without review")

    revision_number = current_revision.revision + 1
    revision_token = f"{fingerprint.fingerprint}:r{revision_number}"
    entitlement = EntitlementBasis.create(
        entitlement_id=service._id(tenant, f"case:{revision_token}:basis"),
        tenant_id=tenant,
        domain=service.vertical,
        source_evidence_ids=tuple(item.evidence_id for item in evidence),
        rule_ref="authorized-immutable-originals-v1-pre-review",
        confidence="PARTIAL" if not effective_missing else "UNRESOLVED",
    )
    calculation = CalculationRecord.create(
        calculation_id=service._id(tenant, f"case:{revision_token}:net-potential"),
        tenant_id=tenant,
        formula_id="industrial_net_potential_claim",
        formula_version="1",
        inputs=tuple(
            CalculationInput(
                name=name,
                value=str(value),
                unit=currency_code,
                evidence_ids=(cost.evidence_id, basis.evidence_id),
            )
            for name, value in amounts.items()
        ),
        output_value=net_potential,
        output_unit=currency_code,
    )
    deadline = DeadlineWindow.create(
        deadline_id=service._id(tenant, f"case:{revision_token}:notice"),
        tenant_id=tenant,
        due_date=notice_due or date.max,
        basis_evidence_ids=(basis.evidence_id, event.evidence_id),
    )
    documentary_complete = not effective_missing
    state = "READY_FOR_REVIEW" if documentary_complete and net_potential > 0 else "UNRESOLVED_EVIDENCE"
    finding = FindingRecord.create(
        finding_id=service._id(tenant, f"case:{revision_token}:finding"),
        tenant_id=tenant,
        finding_type="industrial_recovery_candidate",
        evidence_ids=tuple(item.evidence_id for item in evidence),
        calculation_ids=(calculation.calculation_id,),
        state=state,
    )
    context = TenantContext(tenant_id=tenant, actor_id=actor, roles=("analyst",))
    assert_same_tenant(*evidence, calculation, deadline, finding)
    assert_tenant_context(context, *evidence, calculation, deadline, finding)

    source_authentication_states = {
        item.source_type: str(item.metadata.get("source_authentication") or "UNVERIFIED").strip().upper()
        for item in evidence
    }
    audit = AuditEvent.create(
        event_id=service._id(tenant, f"case:{revision_token}:audit"),
        context=context,
        event_type="industrial_finding_created",
        subject_ref=finding.finding_id,
        evidence_refs=finding.evidence_ids,
        payload={
            "claim_family": family,
            "documentary_complete": documentary_complete,
            "calculation_hash": calculation.reproducibility_hash,
            "entitlement_basis_hash": entitlement.basis_hash,
            "recovery_fingerprint": fingerprint.fingerprint,
            "currency": currency_code,
            "notice_deadline_state": notice_deadline_state,
            "revision": revision_number,
            "supersedes_finding_id": finding_key,
            "evidence_custody_state": "AUTHORIZED_IMMUTABLE_ORIGINALS",
            "source_authentication_states": source_authentication_states,
            "intake_authorization_id": authorization_id,
            "intake_authorization_scope_sha256": authorization_scope_sha256,
            "missing_evidence": sorted(effective_missing),
        },
    )
    notification = NotificationEvent.create(
        event_id=service._id(tenant, f"case:{revision_token}:notification"),
        tenant_id=tenant,
        event_type="finding_ready" if state == "READY_FOR_REVIEW" else "finding_unresolved",
        subject_ref=finding.finding_id,
        payload={
            "vertical": service.vertical,
            "claim_family": family,
            "state": state,
            "currency": currency_code,
            "revision": revision_number,
        },
    )
    case_metadata = IndustrialCaseMetadata(
        finding_id=finding.finding_id,
        tenant_id=tenant,
        claim_family=family,
        customer_ref=customer,
        program_ref=program,
        event_ref=event_key,
        entitlement_id=entitlement.entitlement_id,
        deadline_id=deadline.deadline_id,
        recovery_fingerprint=fingerprint.fingerprint,
        notice_deadline_state=notice_deadline_state,
        missing_evidence=tuple(sorted(effective_missing)),
    )

    old_evidence_ids = tuple(str(item["evidence_id"]) for item in detail["evidence_index"])
    superseded_audit = AuditEvent.create(
        event_id=service._id(tenant, f"case:{revision_token}:supersedes"),
        context=context,
        event_type="industrial_finding_superseded",
        subject_ref=finding_key,
        evidence_refs=old_evidence_ids,
        payload={
            "new_finding_id": finding.finding_id,
            "revision": revision_number,
            "recovery_fingerprint": fingerprint.fingerprint,
            "replacement_evidence_ids": sorted(item.evidence_id for item in evidence),
            "evidence_custody_state": "AUTHORIZED_IMMUTABLE_ORIGINALS",
            "intake_authorization_id": authorization_id,
            "intake_authorization_scope_sha256": authorization_scope_sha256,
        },
    )

    with service.store.transaction() as conn:
        row = conn.execute(
            "SELECT state FROM findings WHERE tenant_id=? AND finding_id=?",
            (tenant, finding_key),
        ).fetchone()
        if row is None:
            raise AssuranceStoreError("tenant-scoped industrial finding not found during amendment")
        if str(row["state"]) not in AMENDABLE_STATES:
            raise AssuranceOperationError(
                "only unresolved, review-ready, approved or rejected findings may be amended"
            )
        if service.index.register_fingerprint(fingerprint, connection=conn):
            raise AssuranceStoreError("amendment cannot register a new recovery fingerprint")
        service.index.put_entitlement(entitlement, connection=conn)
        service.case_store.put(case_metadata, connection=conn)
        service.store.persist_case(
            evidence=evidence,
            calculation=calculation,
            deadline=deadline,
            finding=finding,
            audit=audit,
            notification=notification,
            connection=conn,
        )
        service.revision_store.supersede(
            tenant_id=tenant,
            recovery_fingerprint=fingerprint.fingerprint,
            current_finding_id=finding_key,
            new_finding_id=finding.finding_id,
            connection=conn,
        )
        service.store._append_audit(conn, superseded_audit)

    return IndustrialClaimResult(
        tenant_id=tenant,
        claim_family=family,
        evidence=evidence,
        entitlement=entitlement,
        fingerprint=fingerprint,
        calculation=calculation,
        deadline=deadline,
        notice_deadline_state=notice_deadline_state,
        finding=finding,
        audit=audit,
        notification=notification,
        missing_evidence=tuple(sorted(effective_missing)),
        is_new_recovery=False,
    )
