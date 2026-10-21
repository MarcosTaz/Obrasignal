from __future__ import annotations

from decimal import Decimal

from .models import (
    BlockerType,
    EvidenceKind,
    ProjectCashInput,
    ReconciliationResult,
    RecoveryCase,
    TruthState,
    verified_evidence,
)


ZERO = Decimal("0")


def _non_negative(value: Decimal | None, name: str) -> Decimal | None:
    if value is None:
        return None
    if value < ZERO:
        raise ValueError(f"{name} cannot be negative")
    return value


def _require_verified(input_: ProjectCashInput, kind: EvidenceKind) -> tuple[str, ...]:
    items = verified_evidence(input_.evidence, kind)
    return tuple(item.evidence_id for item in items)


def _case(
    input_: ProjectCashInput,
    *,
    category: str,
    amount: Decimal,
    blocker: BlockerType | None,
    evidence_ids: tuple[str, ...],
    confidence: str,
    action: str,
) -> RecoveryCase:
    # Never promote a positive amount to evidence-supported recovery without evidence.
    state = (
        TruthState.EVIDENCE_SUPPORTED
        if amount > ZERO and evidence_ids
        else TruthState.UNKNOWN
    )
    return RecoveryCase(
        tenant_id=input_.tenant_id,
        customer_id=input_.customer_id,
        project_id=input_.project_id,
        currency=input_.currency,
        category=category,
        amount=amount,
        state=state,
        blocker=blocker,
        evidence_ids=evidence_ids,
        confidence=confidence if evidence_ids else "UNKNOWN",
        action=action if evidence_ids else "REVIEW_EVIDENCE",
    )


def reconcile_project(input_: ProjectCashInput) -> ReconciliationResult:
    certified = _non_negative(input_.certified_value, "certified_value")
    invoiced = _non_negative(input_.invoiced_value, "invoiced_value")
    paid = _non_negative(input_.paid_value, "paid_value")
    retention = _non_negative(input_.retention_held, "retention_held")
    final_account = _non_negative(
        input_.final_account_agreed_value, "final_account_agreed_value"
    )
    disputed = _non_negative(input_.disputed_value, "disputed_value") or ZERO
    deductions = _non_negative(input_.valid_deductions, "valid_deductions") or ZERO

    cases: list[RecoveryCase] = []
    potentially_recoverable = ZERO
    not_yet_due = ZERO
    unknown = False

    # `paid_value` is an operational input, not proof of cash. Only payment
    # evidence with explicit verified amounts can establish VERIFIED_CASH.
    payment_evidence = verified_evidence(input_.evidence, EvidenceKind.PAYMENT)
    payment_amounts = [item.amount for item in payment_evidence]
    payment_evidence_complete = bool(payment_evidence) and all(
        amount is not None for amount in payment_amounts
    )
    payment_evidence_total = (
        sum((amount for amount in payment_amounts if amount is not None), ZERO)
        if payment_evidence_complete
        else ZERO
    )
    if (paid or ZERO) == ZERO:
        verified_paid = ZERO
    elif payment_evidence_complete and payment_evidence_total == paid:
        verified_paid = paid
    else:
        verified_paid = ZERO
        unknown = True

    # Fail closed if core cash chain is materially inconsistent.
    if certified is not None and invoiced is not None and invoiced > certified:
        # This can be legitimate in unusual contract structures, but it cannot be
        # safely interpreted without review.
        return ReconciliationResult(
            project_id=input_.project_id,
            currency=input_.currency,
            cases=(),
            verified_paid=verified_paid,
            potentially_recoverable=ZERO,
            not_yet_due=ZERO,
            disputed=disputed,
            unknown=True,
        )
    if paid is not None and invoiced is not None and paid > invoiced:
        return ReconciliationResult(
            project_id=input_.project_id,
            currency=input_.currency,
            cases=(),
            verified_paid=verified_paid,
            potentially_recoverable=ZERO,
            not_yet_due=ZERO,
            disputed=disputed,
            unknown=True,
        )

    # Certified but not invoiced: only surface if certification evidence exists.
    if certified is not None and invoiced is not None and certified > invoiced:
        amount = certified - invoiced
        evidence_ids = _require_verified(input_, EvidenceKind.CERTIFICATE)
        case = _case(
            input_,
            category="CERTIFIED_NOT_INVOICED",
            amount=amount,
            blocker=BlockerType.INVOICE_MISSING,
            evidence_ids=evidence_ids,
            confidence="HIGH",
            action="PREPARE_INVOICE_RECONCILIATION",
        )
        cases.append(case)
        if case.state == TruthState.EVIDENCE_SUPPORTED:
            potentially_recoverable += amount
        else:
            unknown = True

    # Invoiced unpaid balance. Do not call it overdue unless payment_due is explicit.
    if invoiced is not None and paid is not None and invoiced > paid:
        gross_open = invoiced - paid
        net_open = max(ZERO, gross_open - disputed - deductions)
        if net_open > ZERO:
            invoice_ids = _require_verified(input_, EvidenceKind.INVOICE)
            if input_.payment_due is True:
                case = _case(
                    input_,
                    category="INVOICED_DUE_UNPAID",
                    amount=net_open,
                    blocker=BlockerType.PAYMENT_DELAY,
                    evidence_ids=invoice_ids,
                    confidence="HIGH",
                    action="PREPARE_PAYMENT_EVIDENCE_PACKAGE",
                )
                cases.append(case)
                if case.state == TruthState.EVIDENCE_SUPPORTED:
                    potentially_recoverable += net_open
                else:
                    unknown = True
            elif input_.payment_due is False:
                not_yet_due += net_open
            else:
                unknown = True

    # Retention is separate from ordinary invoiced balance to avoid double-counting.
    if retention is not None and retention > ZERO:
        retention_ids = _require_verified(input_, EvidenceKind.RETENTION_RELEASE)
        if input_.retention_matured is True:
            case = _case(
                input_,
                category="RETENTION_MATURED_UNRELEASED",
                amount=retention,
                blocker=BlockerType.PAYMENT_DELAY,
                evidence_ids=retention_ids,
                confidence="HIGH",
                action="PREPARE_RETENTION_RELEASE_PACKAGE",
            )
            cases.append(case)
            if case.state == TruthState.EVIDENCE_SUPPORTED:
                potentially_recoverable += retention
            else:
                unknown = True
        elif input_.retention_matured is False:
            not_yet_due += retention
        else:
            unknown = True

    # Final account agreed balance: surface only from independently verified final account.
    if final_account is not None and paid is not None and final_account > paid:
        balance = max(ZERO, final_account - paid - disputed - deductions)
        if balance > ZERO:
            final_ids = _require_verified(input_, EvidenceKind.FINAL_ACCOUNT)
            if input_.payment_due is True:
                case = _case(
                    input_,
                    category="FINAL_ACCOUNT_AGREED_UNPAID",
                    amount=balance,
                    blocker=BlockerType.PAYMENT_DELAY,
                    evidence_ids=final_ids,
                    confidence="HIGH",
                    action="PREPARE_FINAL_ACCOUNT_PAYMENT_PACKAGE",
                )
                # De-duplicate against an identical invoiced balance.
                duplicate = any(
                    c.amount == case.amount and c.category == "INVOICED_DUE_UNPAID"
                    for c in cases
                )
                if not duplicate:
                    cases.append(case)
                    if case.state == TruthState.EVIDENCE_SUPPORTED:
                        potentially_recoverable += balance
                    else:
                        unknown = True
            elif input_.payment_due is False:
                not_yet_due = max(not_yet_due, balance)
            else:
                unknown = True

    return ReconciliationResult(
        project_id=input_.project_id,
        currency=input_.currency,
        cases=tuple(cases),
        verified_paid=verified_paid,
        potentially_recoverable=potentially_recoverable,
        not_yet_due=not_yet_due,
        disputed=disputed,
        unknown=unknown,
    )
