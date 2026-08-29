from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .store import EarnedCashStore


ZERO = Decimal("0")


@dataclass(frozen=True)
class CaseCashAttribution:
    case_id: str
    receipt_id: str
    project_id: str
    amount: Decimal
    currency: str
    evidence_ref: str


@dataclass(frozen=True)
class AttributionResult:
    attributions: tuple[CaseCashAttribution, ...]
    verified_total: Decimal
    valid: bool
    issues: tuple[str, ...]


def _amount(value) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < ZERO:
        return None
    return parsed


def verified_case_cash_attribution(
    store: EarnedCashStore,
    *,
    tenant_id: str,
    project_id: str,
) -> AttributionResult:
    """Join paid-case and cash-receipt audit events by exact evidence reference.

    This is the fee-attribution boundary. Project cash without a matching PAID
    case transition is intentionally excluded. Invalid/tampered audit history
    fails closed to zero verified attribution.
    """
    if not store.audit_valid(tenant_id):
        return AttributionResult((), ZERO, False, ("AUDIT_CHAIN_INVALID",))

    history = store.audit_history(tenant_id)
    paid_by_ref: dict[str, tuple[str, str]] = {}
    cash_by_ref: dict[str, tuple[str, str, Decimal, str]] = {}
    issues: list[str] = []

    for event in history:
        payload = event.payload
        if event.event_type == "CASE_STATE_CHANGED":
            if payload.get("project_id") != project_id or payload.get("to") != "PAID":
                continue
            evidence_ref = str(payload.get("cash_evidence_ref") or "").strip()
            if not evidence_ref:
                issues.append(f"PAID_CASE_WITHOUT_CASH_REF:{event.entity_id}")
                continue
            if evidence_ref in paid_by_ref:
                issues.append(f"DUPLICATE_PAID_EVIDENCE_REF:{evidence_ref}")
                continue
            paid_by_ref[evidence_ref] = (event.entity_id, project_id)

        elif event.event_type == "VERIFIED_CASH_RECORDED":
            if payload.get("project_id") != project_id:
                continue
            evidence_ref = str(payload.get("evidence_ref") or "").strip()
            amount = _amount(payload.get("amount"))
            currency = str(payload.get("currency") or "").strip().upper()
            if not evidence_ref or amount is None or not currency:
                issues.append(f"INVALID_CASH_EVENT:{event.entity_id}")
                continue
            if evidence_ref in cash_by_ref:
                issues.append(f"DUPLICATE_CASH_EVIDENCE_REF:{evidence_ref}")
                continue
            cash_by_ref[evidence_ref] = (
                event.entity_id,
                project_id,
                amount,
                currency,
            )

    cases = {
        case["case_id"]: case
        for case in store.list_cases(tenant_id=tenant_id, project_id=project_id)
    }
    attributions: list[CaseCashAttribution] = []
    for evidence_ref, (case_id, _) in paid_by_ref.items():
        cash = cash_by_ref.get(evidence_ref)
        if cash is None:
            issues.append(f"PAID_CASE_WITHOUT_MATCHING_CASH:{case_id}")
            continue
        case = cases.get(case_id)
        if case is None:
            issues.append(f"ATTRIBUTED_CASE_NOT_FOUND:{case_id}")
            continue
        if case.get("status") != "PAID":
            issues.append(f"ATTRIBUTED_CASE_NOT_CURRENTLY_PAID:{case_id}")
            continue
        case_amount = _amount(case.get("amount"))
        receipt_id, _, amount, currency = cash
        if case_amount is None or amount != case_amount:
            issues.append(f"ATTRIBUTED_AMOUNT_MISMATCH:{case_id}")
            continue
        if currency != str(case.get("currency") or "").upper():
            issues.append(f"ATTRIBUTED_CURRENCY_MISMATCH:{case_id}")
            continue
        attributions.append(
            CaseCashAttribution(
                case_id=case_id,
                receipt_id=receipt_id,
                project_id=project_id,
                amount=amount,
                currency=currency,
                evidence_ref=evidence_ref,
            )
        )

    # Cash can exist in the project without being incremental recovery cash. It is
    # valid project cash, but not a fee-bearing attribution and is deliberately
    # excluded rather than treated as an error.
    attributions.sort(key=lambda item: (item.case_id, item.receipt_id))
    verified_total = sum((item.amount for item in attributions), ZERO)
    valid = not issues
    return AttributionResult(
        tuple(attributions),
        verified_total if valid else ZERO,
        valid,
        tuple(sorted(issues)),
    )
