from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from finding_store import FindingStore
from repository import NotFoundError, RoyaltyRepository


OUTCOME_TYPES = {"NO_ADJUSTMENT", "ADJUSTMENT_CONFIRMED", "SETTLED", "CLOSED"}
RECOVERY_ELIGIBLE_OUTCOMES = {"ADJUSTMENT_CONFIRMED", "SETTLED"}
RECOVERY_ELIGIBLE_REVIEW_STATES = {"DESK_APPROVED", "FORMAL_AUDIT_ROUTE"}


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _required(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _money(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid money amount") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("money amount must be finite and positive")
    return amount


class OutcomeStore:
    def __init__(self, repository: RoyaltyRepository):
        self.repo = repository
        self.conn = repository.conn
        self.findings = FindingStore(repository)

    def record_payment(self, org_id: str, agreement_id: str, payment_date: str, currency: str, amount, evidence_id: str, actor_id: str, payment_reference: Optional[str] = None) -> dict[str, Any]:
        self.repo.get_agreement(org_id, agreement_id)
        evidence = self.repo.get_evidence(org_id, evidence_id)
        payment_date = _required(payment_date, "payment_date")
        currency = _required(currency, "currency").upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        amount_decimal = _money(amount)
        payment_id = _id("payment")
        self.conn.execute(
            """INSERT INTO payments(id, agreement_id, payment_date, currency, amount_decimal, payment_reference, evidence_id)
               VALUES(?,?,?,?,?,?,?)""",
            (payment_id, agreement_id, payment_date, currency, format(amount_decimal, "f"), payment_reference, evidence["id"]),
        )
        self.repo._audit(org_id, actor_id, "CREATE", "Payment", payment_id, {
            "agreement_id": agreement_id, "currency": currency, "amount_decimal": format(amount_decimal, "f"), "evidence_id": evidence["id"],
        })
        self.conn.commit()
        return self.get_payment(org_id, payment_id)

    def get_payment(self, org_id: str, payment_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT p.* FROM payments p
               JOIN agreements a ON a.id=p.agreement_id
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE p.id=? AND l.organization_id=? AND e.organization_id=?""",
            (payment_id, org_id, org_id),
        ).fetchone()
        if not row:
            raise NotFoundError("payment not found in organization scope")
        return dict(row)

    def record_outcome(self, org_id: str, finding_id: str, outcome_type: str, actor_id: str, *, evidence_id: Optional[str] = None, notes: Optional[str] = None, resolved_at: Optional[str] = None) -> dict[str, Any]:
        finding = self.findings.get_finding(org_id, finding_id)
        outcome_type = _required(outcome_type, "outcome_type").upper()
        if outcome_type not in OUTCOME_TYPES:
            raise ValueError("unsupported outcome type")
        if outcome_type in RECOVERY_ELIGIBLE_OUTCOMES:
            if finding["review_status"] not in RECOVERY_ELIGIBLE_REVIEW_STATES:
                raise ValueError("recovery-bearing outcome requires a reviewer-approved candidate")
            if not evidence_id:
                raise ValueError("recovery-bearing outcome requires external outcome evidence")
        if evidence_id is not None:
            self.repo.get_evidence(org_id, evidence_id)
        outcome_id = _id("outcome")
        self.conn.execute(
            "INSERT INTO outcomes(id, claim_id, finding_id, outcome_type, resolved_at, notes) VALUES(?,NULL,?,?,?,?)",
            (outcome_id, finding_id, outcome_type, resolved_at, notes),
        )
        self.repo._audit(org_id, actor_id, "CREATE", "Outcome", outcome_id, {
            "finding_id": finding["id"], "outcome_type": outcome_type, "evidence_id": evidence_id,
        })
        self.conn.commit()
        return self.get_outcome(org_id, outcome_id)

    def get_outcome(self, org_id: str, outcome_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT o.* FROM outcomes o
               JOIN findings f ON f.id=o.finding_id
               JOIN agreements a ON a.id=f.agreement_id
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE o.id=? AND l.organization_id=? AND e.organization_id=?""",
            (outcome_id, org_id, org_id),
        ).fetchone()
        if not row:
            raise NotFoundError("outcome not found in organization scope")
        return dict(row)

    def record_recovered_amount_candidate(self, org_id: str, outcome_id: str, payment_id: str, amount, currency: str, evidence_id: str, actor_id: str) -> dict[str, Any]:
        outcome = self.get_outcome(org_id, outcome_id)
        if outcome["outcome_type"] not in RECOVERY_ELIGIBLE_OUTCOMES:
            raise ValueError("outcome type does not support a recovered-amount record")
        finding = self.findings.get_finding(org_id, outcome["finding_id"])
        if finding["review_status"] not in RECOVERY_ELIGIBLE_REVIEW_STATES:
            raise ValueError("finding is not in an approved recovery-outcome state")
        payment = self.get_payment(org_id, payment_id)
        if payment["agreement_id"] != finding["agreement_id"]:
            raise ValueError("payment belongs to a different agreement")
        evidence = self.repo.get_evidence(org_id, evidence_id)
        amount_decimal = _money(amount)
        currency = _required(currency, "currency").upper()
        if currency != payment["currency"]:
            raise ValueError("recovered amount currency must match payment currency")
        if amount_decimal > Decimal(payment["amount_decimal"]):
            raise ValueError("recovered amount cannot exceed evidenced payment")
        recovered_id = _id("recovered")
        self.conn.execute(
            """INSERT INTO recovered_amounts(id, outcome_id, payment_id, amount_decimal, currency, incremental_status, evidence_id)
               VALUES(?,?,?,?,?,'UNVERIFIED',?)""",
            (recovered_id, outcome_id, payment_id, format(amount_decimal, "f"), currency, evidence["id"]),
        )
        self.repo._audit(org_id, actor_id, "CREATE", "RecoveredAmount", recovered_id, {
            "outcome_id": outcome_id, "payment_id": payment_id, "amount_decimal": format(amount_decimal, "f"),
            "currency": currency, "evidence_id": evidence["id"], "incremental_status": "UNVERIFIED",
        })
        self.conn.commit()
        return self.get_recovered_amount(org_id, recovered_id)

    def get_recovered_amount(self, org_id: str, recovered_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT r.* FROM recovered_amounts r
               JOIN outcomes o ON o.id=r.outcome_id
               JOIN findings f ON f.id=o.finding_id
               JOIN agreements a ON a.id=f.agreement_id
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE r.id=? AND l.organization_id=? AND e.organization_id=?""",
            (recovered_id, org_id, org_id),
        ).fetchone()
        if not row:
            raise NotFoundError("recovered amount not found in organization scope")
        return dict(row)

    def verify_recovered_amount(self, org_id: str, recovered_id: str, reviewer_id: str, rationale: str) -> dict[str, Any]:
        recovered = self.get_recovered_amount(org_id, recovered_id)
        reviewer_id = _required(reviewer_id, "reviewer_id")
        rationale = _required(rationale, "rationale")
        payment = self.get_payment(org_id, recovered["payment_id"])
        evidence = self.repo.get_evidence(org_id, recovered["evidence_id"])
        if Decimal(recovered["amount_decimal"]) > Decimal(payment["amount_decimal"]):
            raise ValueError("recovery cannot be verified above evidenced payment")
        self.conn.execute("UPDATE recovered_amounts SET incremental_status='VERIFIED_PAYMENT' WHERE id=?", (recovered_id,))
        self.repo._audit(org_id, reviewer_id, "VERIFY", "RecoveredAmount", recovered_id, {
            "rationale": rationale, "payment_id": payment["id"], "evidence_id": evidence["id"], "incremental_status": "VERIFIED_PAYMENT",
        })
        self.conn.commit()
        return self.get_recovered_amount(org_id, recovered_id)

    def verified_summary(self, org_id: str) -> dict[str, Any]:
        self.repo._require_org(org_id)
        rows = self.conn.execute(
            """SELECT r.amount_decimal, r.currency FROM recovered_amounts r
               JOIN outcomes o ON o.id=r.outcome_id
               JOIN findings f ON f.id=o.finding_id
               JOIN agreements a ON a.id=f.agreement_id
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE l.organization_id=? AND e.organization_id=? AND r.incremental_status='VERIFIED_PAYMENT'""",
            (org_id, org_id),
        ).fetchall()
        currencies = {row["currency"] for row in rows}
        total = None
        currency = None
        if len(currencies) == 1:
            currency = next(iter(currencies))
            total = sum((Decimal(row["amount_decimal"]) for row in rows), Decimal("0"))
        return {
            "verified_recovery_count": len(rows),
            "verified_recovery_total": None if total is None else format(total, "f"),
            "currency": currency,
            "mixed_currency_total_suppressed": len(currencies) > 1,
        }
