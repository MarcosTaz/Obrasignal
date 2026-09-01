from __future__ import annotations

from factory_cloud.assurance_ops import AssuranceOperationError
from vertical_apps.industrial_claims.secure_outcome_registry import SecureOutcomeRegistry


class SecureOutcomeResolutionError(RuntimeError):
    pass


def resolve_from_secure_outcome(
    service,
    registry: SecureOutcomeRegistry,
    *,
    tenant_id: str,
    finding_id: str,
    outcome_id: str,
    recovered_amount: str,
    currency: str,
    evidence_id: str,
    evidence_ref: str,
    actor_id: str,
    final_cumulative: bool,
):
    """Close an ACTIONED finding using an already-authorized immutable outcome original.

    This path accepts identifiers only. It proves custody/integrity of the outcome
    document but does not infer payment authenticity or economic/legal effect from
    the document merely being present.
    """
    from vertical_apps.industrial_claims.service import (
        MAX_ACTOR_CHARS,
        MAX_FINDING_ID_CHARS,
        MAX_REFERENCE_CHARS,
    )

    if final_cumulative is not True:
        raise SecureOutcomeResolutionError(
            "final_cumulative must be true because secure resolution closes the finding"
        )
    tenant = service._operation_tenant_id(tenant_id)
    finding_key = service._bounded_operation_text(
        finding_id,
        label="finding_id",
        max_chars=MAX_FINDING_ID_CHARS,
    )
    outcome_key = service._bounded_operation_text(
        outcome_id,
        label="outcome_id",
        max_chars=MAX_REFERENCE_CHARS,
    )
    evidence_key = service._bounded_operation_text(
        evidence_id,
        label="outcome evidence id",
        max_chars=MAX_FINDING_ID_CHARS,
    )
    evidence_reference = service._bounded_operation_text(
        evidence_ref,
        label="outcome evidence ref",
        max_chars=MAX_REFERENCE_CHARS,
    )
    actor = service._bounded_operation_text(
        actor_id,
        label="resolution actor",
        max_chars=MAX_ACTOR_CHARS,
    )
    amount = service._operation_amount(recovered_amount, label="recovered amount")
    if amount < 0:
        raise AssuranceOperationError("recovered amount cannot be negative")
    recovery_currency = str(currency or "").strip().upper()
    if len(recovery_currency) != 3 or not recovery_currency.isalpha() or not recovery_currency.isascii():
        raise AssuranceOperationError("recovery currency must be a three-letter ASCII code")

    service._assert_dossier_integrity(tenant_id=tenant, finding_id=finding_key)
    maximum, reviewed_currency = service._reviewed_net_potential(
        tenant_id=tenant,
        finding_id=finding_key,
    )
    if recovery_currency != reviewed_currency:
        raise AssuranceOperationError("recovery currency does not match reviewed claim currency")
    if amount > maximum:
        raise AssuranceOperationError(
            "recovered amount exceeds reviewed net potential; amend and re-review the finding"
        )

    evidence = registry.get(
        tenant_id=tenant,
        evidence_id=evidence_key,
        finding_id=finding_key,
        source_ref=evidence_reference,
    )
    scoped_outcome_id = service._id(tenant, outcome_key)
    with service.store.transaction() as conn:
        service.store._put_evidence(conn, evidence)
        return service.ops.resolve(
            tenant_id=tenant,
            finding_id=finding_key,
            outcome_id=scoped_outcome_id,
            recovered_amount=str(amount),
            currency=recovery_currency,
            evidence_ref=evidence.evidence_id,
            actor_id=actor,
            connection=conn,
        )
