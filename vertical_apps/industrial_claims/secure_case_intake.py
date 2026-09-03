from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
from typing import TYPE_CHECKING, Mapping

from factory_cloud.assurance_kernel import (
    AssuranceKernelError,
    CalculationInput,
    CalculationRecord,
    DeadlineWindow,
    EvidenceEnvelope,
    FindingRecord,
    assert_same_tenant,
)
from factory_cloud.assurance_store import AssuranceStoreError
from factory_cloud.recovery_primitives import EntitlementBasis, RecoveryFingerprint
from factory_cloud.shared_platform import AuditEvent, NotificationEvent, TenantContext, assert_tenant_context
from vertical_apps.industrial_claims.case_store import IndustrialCaseMetadata
from vertical_apps.industrial_claims.intake_authorization import BOUNDED_RAPID_SCAN_PURPOSE
from vertical_apps.industrial_claims.revision_store import IndustrialCaseRevision
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry

if TYPE_CHECKING:
    from vertical_apps.industrial_claims.service import IndustrialClaimResult, IndustrialClaimsService


class SecureCaseIntakeError(RuntimeError):
    pass


_REQUIRED_ROLES = ("commercial_basis", "event", "cost")
_ROLE_SOURCE_TYPES = {
    "commercial_basis": "commercial_basis",
    "event": "industrial_commercial_event",
    "cost": "cost_evidence",
}


def _true(value: object) -> bool:
    return value is True or str(value or "").strip().lower() == "true"


def _required_metadata_text(metadata: Mapping[str, object], key: str) -> str:
    value = str(metadata.get(key) or "").strip()
    if not value:
        raise SecureCaseIntakeError(f"secure case evidence is missing {key}")
    return value


def _assert_real_original_assurance(item: EvidenceEnvelope, *, role: str) -> None:
    metadata = dict(item.metadata or {})
    if item.source_type != _ROLE_SOURCE_TYPES[role]:
        raise SecureCaseIntakeError("secure case evidence role/source binding mismatch")
    if str(metadata.get("capture_mode") or "") != "DIRECT_SECURE_ORIGINAL_CAPTURE":
        raise SecureCaseIntakeError("secure case evidence is not a direct original capture")
    if not _true(metadata.get("raw_content_persisted")):
        raise SecureCaseIntakeError("secure case original bytes are not durably persisted")
    if not _true(metadata.get("original_version_readback_verified")):
        raise SecureCaseIntakeError("secure case original exact-version readback is not verified")
    if not _true(metadata.get("proof_integrity_sealed")):
        raise SecureCaseIntakeError("secure case original integrity seal is not verified")
    if str(metadata.get("immutability") or "").strip().upper() != "WORM_LOCKED":
        raise SecureCaseIntakeError("secure case original is not WORM locked")
    if not _true(metadata.get("worm_lock_verified")):
        raise SecureCaseIntakeError("secure case WORM lock is not verified")
    if str(metadata.get("original_retention_mode") or "").strip().upper() != "COMPLIANCE":
        raise SecureCaseIntakeError("secure case original is not under COMPLIANCE retention")
    if str(metadata.get("intake_purpose") or "").strip().upper() != BOUNDED_RAPID_SCAN_PURPOSE:
        raise SecureCaseIntakeError("secure case evidence is outside bounded rapid-scan purpose")
    if str(metadata.get("intake_evidence_role") or "").strip().lower() != role:
        raise SecureCaseIntakeError("secure case evidence intake role mismatch")

    sha512 = str(metadata.get("content_sha512") or "").strip().lower()
    if len(sha512) != 128 or any(ch not in "0123456789abcdef" for ch in sha512):
        raise SecureCaseIntakeError("secure case original SHA-512 binding is invalid")


def _load_case_evidence(
    registry: SecureCaptureRegistry,
    *,
    tenant_id: str,
    intake_case_ref: str,
    evidence_ids: Mapping[str, str],
    source_refs: Mapping[str, str],
) -> tuple[tuple[EvidenceEnvelope, ...], str, str]:
    if set(evidence_ids) != set(_REQUIRED_ROLES):
        raise SecureCaseIntakeError("secure case requires exactly commercial_basis, event and cost evidence ids")
    if set(source_refs) != set(_REQUIRED_ROLES):
        raise SecureCaseIntakeError("secure case requires exactly commercial_basis, event and cost source refs")

    loaded: list[EvidenceEnvelope] = []
    common_scope: tuple[str, ...] | None = None
    authorization_id = ""
    scope_sha256 = ""
    for role in _REQUIRED_ROLES:
        evidence_id = str(evidence_ids[role] or "").strip()
        source_ref = str(source_refs[role] or "").strip()
        if not evidence_id or not source_ref:
            raise SecureCaseIntakeError("secure case evidence id and source ref are required")
        item = registry.get(
            tenant_id=tenant_id,
            evidence_id=evidence_id,
            evidence_role=role,
            source_ref=source_ref,
        )
        _assert_real_original_assurance(item, role=role)
        metadata = dict(item.metadata or {})
        case_ref = _required_metadata_text(metadata, "intake_case_ref")
        if case_ref != intake_case_ref:
            raise SecureCaseIntakeError("secure evidence does not belong to requested intake case")

        scope = (
            _required_metadata_text(metadata, "intake_authorization_id"),
            _required_metadata_text(metadata, "intake_authorization_scope_sha256").lower(),
            case_ref,
            _required_metadata_text(metadata, "intake_purpose").upper(),
            _required_metadata_text(metadata, "intake_authorized_at"),
            _required_metadata_text(metadata, "intake_authorization_expires_at"),
            _required_metadata_text(metadata, "intake_minimum_immutable_retention_until"),
            _required_metadata_text(metadata, "intake_data_terms_state").upper(),
            _required_metadata_text(metadata, "intake_authorized_by_sha256").lower(),
            _required_metadata_text(metadata, "intake_transfer_channel_sha256").lower(),
            str(metadata.get("intake_max_bytes_per_evidence") or "").strip(),
        )
        if common_scope is None:
            common_scope = scope
            authorization_id = scope[0]
            scope_sha256 = scope[1]
        elif scope != common_scope:
            raise SecureCaseIntakeError("secure case evidence does not share one intake authorization scope")
        loaded.append(item)

    if len(scope_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in scope_sha256):
        raise SecureCaseIntakeError("secure case intake scope hash is invalid")
    return tuple(loaded), authorization_id, scope_sha256


def create_case_from_secure_capture(
    service: "IndustrialClaimsService",
    registry: SecureCaptureRegistry,
    *,
    tenant_id: str,
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
    """Create a real-case candidate from already-authorized immutable originals.

    No raw bytes are accepted here and no external provider is called. The exact
    EvidenceEnvelope records previously registered by SecureCaptureRegistry become
    the finding's documentary lineage. This function proves controlled custody and
    immutable capture only; source authenticity and legal recoverability remain
    separate truth dimensions.
    """
    from vertical_apps.industrial_claims.service import (
        ALLOWED_CLAIM_FAMILIES,
        CLAIM_CURRENCY_EVIDENCE,
        DECIMAL_WORKING_PRECISION,
        MAX_ACTOR_CHARS,
        MAX_REFERENCE_CHARS,
        NOTICE_DEADLINE_EVIDENCE,
        IndustrialClaimResult,
    )

    tenant = service._tenant_id(tenant_id)
    actor = service._bounded_text(actor_id, label="actor_id", max_chars=MAX_ACTOR_CHARS)
    intake_ref = service._bounded_text(intake_case_ref, label="intake_case_ref", max_chars=MAX_REFERENCE_CHARS)
    customer = service._bounded_text(customer_ref, label="customer_ref", max_chars=MAX_REFERENCE_CHARS)
    program = service._bounded_text(program_ref, label="program_ref", max_chars=MAX_REFERENCE_CHARS)
    event_key = service._bounded_text(event_ref, label="event_ref", max_chars=MAX_REFERENCE_CHARS)
    basis_ref = service._bounded_text(commercial_basis_ref, label="commercial_basis_ref", max_chars=MAX_REFERENCE_CHARS)
    cost_ref = service._bounded_text(cost_evidence_ref, label="cost_evidence_ref", max_chars=MAX_REFERENCE_CHARS)
    family = str(claim_family or "").strip().upper()
    if family not in ALLOWED_CLAIM_FAMILIES:
        raise AssuranceKernelError("unsupported industrial claim family")
    if not isinstance(notice_deadline_not_applicable, bool):
        raise AssuranceKernelError("notice_deadline_not_applicable must be boolean")
    if notice_due is not None and notice_deadline_not_applicable:
        raise AssuranceKernelError("notice due date and declared no-deadline state are mutually exclusive")

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
        raise AssuranceKernelError("industrial claim amounts cannot be negative")
    with localcontext() as decimal_context:
        decimal_context.prec = DECIMAL_WORKING_PRECISION
        deductions = sum((value for key, value in amounts.items() if key != "gross_cost"), Decimal("0"))
        net_potential = amounts["gross_cost"] - deductions
    if net_potential < 0:
        raise AssuranceKernelError("mitigation/recovery cannot exceed gross cost without review")

    fingerprint = RecoveryFingerprint.create(
        tenant_id=tenant,
        vertical=service.vertical,
        contract_ref=service._contract_ref(customer, program, basis_ref),
        event_ref=event_key,
        remedy_type=family.lower(),
    )
    case_token = fingerprint.fingerprint
    entitlement = EntitlementBasis.create(
        entitlement_id=service._id(tenant, f"case:{case_token}:basis"),
        tenant_id=tenant,
        domain=service.vertical,
        source_evidence_ids=tuple(item.evidence_id for item in evidence),
        rule_ref="authorized-immutable-originals-v1-pre-review",
        confidence="PARTIAL" if not effective_missing else "UNRESOLVED",
    )
    calculation = CalculationRecord.create(
        calculation_id=service._id(tenant, f"case:{case_token}:net-potential"),
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
        deadline_id=service._id(tenant, f"case:{case_token}:notice"),
        tenant_id=tenant,
        due_date=notice_due or date.max,
        basis_evidence_ids=(basis.evidence_id, event.evidence_id),
    )
    documentary_complete = not effective_missing
    state = "READY_FOR_REVIEW" if documentary_complete and net_potential > 0 else "UNRESOLVED_EVIDENCE"
    finding = FindingRecord.create(
        finding_id=service._id(tenant, f"case:{case_token}:finding"),
        tenant_id=tenant,
        finding_type="industrial_recovery_candidate",
        evidence_ids=tuple(item.evidence_id for item in evidence),
        calculation_ids=(calculation.calculation_id,),
        state=state,
    )
    context = TenantContext(tenant_id=tenant, actor_id=actor, roles=("analyst",))
    context.require_role("analyst")
    assert_same_tenant(*evidence, calculation, deadline, finding)
    assert_tenant_context(context, *evidence, calculation, deadline, finding)

    source_authentication_states = {
        item.source_type: str(item.metadata.get("source_authentication") or "UNVERIFIED").strip().upper()
        for item in evidence
    }
    audit = AuditEvent.create(
        event_id=service._id(tenant, f"case:{case_token}:audit"),
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
            "evidence_custody_state": "AUTHORIZED_IMMUTABLE_ORIGINALS",
            "source_authentication_states": source_authentication_states,
            "intake_authorization_id": authorization_id,
            "intake_authorization_scope_sha256": authorization_scope_sha256,
            "missing_evidence": sorted(effective_missing),
        },
    )
    notification = NotificationEvent.create(
        event_id=service._id(tenant, f"case:{case_token}:notification"),
        tenant_id=tenant,
        event_type="finding_ready" if state == "READY_FOR_REVIEW" else "finding_unresolved",
        subject_ref=finding.finding_id,
        payload={
            "vertical": service.vertical,
            "claim_family": family,
            "state": state,
            "currency": currency_code,
            "notice_deadline_state": notice_deadline_state,
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
    initial_revision = IndustrialCaseRevision(
        finding_id=finding.finding_id,
        tenant_id=tenant,
        recovery_fingerprint=fingerprint.fingerprint,
        revision=1,
        supersedes_finding_id=None,
        is_current=True,
    )

    with service.store.transaction() as conn:
        is_new = service.index.persist_case_index(entitlement, fingerprint, connection=conn)
        service.case_store.put(case_metadata, connection=conn)
        if is_new:
            service.revision_store.register_initial(initial_revision, connection=conn)
            service.store.persist_case(
                evidence=evidence,
                calculation=calculation,
                deadline=deadline,
                finding=finding,
                audit=audit,
                notification=notification,
                connection=conn,
            )
    if not is_new:
        current_revision = service.revision_store.current_for_fingerprint(
            tenant_id=tenant,
            recovery_fingerprint=fingerprint.fingerprint,
        )
        if current_revision.finding_id != finding.finding_id:
            raise AssuranceStoreError("recovery fingerprint has a newer current revision; use the current finding")
        finding = service._validate_replay_without_state_change(
            evidence=evidence,
            calculation=calculation,
            deadline=deadline,
            finding=finding,
            audit=audit,
            notification=notification,
        )

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
        is_new_recovery=is_new,
    )
