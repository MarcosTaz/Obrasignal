from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from repository import NotFoundError, RoyaltyRepository
from royalty_engine import FindingState


ALLOWED_REVIEW_DECISIONS = {
    "REQUEST_MORE_DATA",
    "REJECT_RECOVERY",
    "APPROVE_DESK_FINDING",
    "ROUTE_TO_FORMAL_AUDIT",
    "REQUIRE_PROFESSIONAL_REVIEW",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _required(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _money(value: Optional[Decimal]) -> Optional[str]:
    return None if value is None else format(value, "f")


class FindingStore:
    def __init__(self, repository: RoyaltyRepository):
        self.repo = repository
        self.conn = repository.conn

    def create_finding(
        self,
        org_id: str,
        agreement_id: str,
        finding_type: str,
        state: FindingState,
        confidence: str,
        actor_id: str,
        *,
        amount: Optional[Decimal] = None,
        currency: Optional[str] = None,
        variance_id: Optional[str] = None,
        source_clause_id: Optional[str] = None,
    ) -> dict[str, Any]:
        self.repo.get_agreement(org_id, agreement_id)
        finding_type = _required(finding_type, "finding_type")
        confidence = _required(confidence, "confidence")
        actor_id = _required(actor_id, "actor_id")
        if amount is not None and amount < 0:
            raise ValueError("finding amount must not be negative")
        if amount is not None and not currency:
            raise ValueError("currency is required when amount is present")
        if state != FindingState.RECOVERY_CANDIDATE and amount not in (None, Decimal("0"), Decimal("0.00")):
            raise ValueError("positive amount is only permitted for RECOVERY_CANDIDATE")
        finding_id = _id("finding")
        self.conn.execute(
            """INSERT INTO findings(
                   id, agreement_id, variance_id, finding_type, state, confidence,
                   amount_decimal, currency, source_clause_id, created_at, review_status
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                finding_id, agreement_id, variance_id, finding_type, state.value, confidence,
                _money(amount), currency, source_clause_id, _now(), "PENDING",
            ),
        )
        self.repo._audit(org_id, actor_id, "CREATE", "Finding", finding_id, {
            "agreement_id": agreement_id,
            "state": state.value,
            "amount_decimal": _money(amount),
            "currency": currency,
        })
        self.conn.commit()
        return self.get_finding(org_id, finding_id)

    def get_finding(self, org_id: str, finding_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT f.* FROM findings f
               JOIN agreements a ON a.id=f.agreement_id
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE f.id=? AND l.organization_id=? AND e.organization_id=?""",
            (finding_id, org_id, org_id),
        ).fetchone()
        if not row:
            raise NotFoundError("finding not found in organization scope")
        return dict(row)

    def add_review(
        self,
        org_id: str,
        finding_id: str,
        reviewer_id: str,
        reviewer_role: str,
        decision: str,
        rationale: str,
    ) -> dict[str, Any]:
        finding = self.get_finding(org_id, finding_id)
        reviewer_id = _required(reviewer_id, "reviewer_id")
        reviewer_role = _required(reviewer_role, "reviewer_role")
        decision = _required(decision, "decision").upper()
        rationale = _required(rationale, "rationale")
        if decision not in ALLOWED_REVIEW_DECISIONS:
            raise ValueError("unsupported review decision")

        if decision in {"APPROVE_DESK_FINDING", "ROUTE_TO_FORMAL_AUDIT"} and finding["state"] != FindingState.RECOVERY_CANDIDATE.value:
            raise ValueError("only a RECOVERY_CANDIDATE may be approved or routed to formal audit")

        review_id = _id("review")
        reviewed_at = _now()
        self.conn.execute(
            "INSERT INTO reviews(id, finding_id, reviewer_role, decision, rationale, reviewed_at) VALUES(?,?,?,?,?,?)",
            (review_id, finding_id, reviewer_role, decision, rationale, reviewed_at),
        )
        review_status = {
            "REQUEST_MORE_DATA": "NEEDS_DATA",
            "REJECT_RECOVERY": "REJECTED",
            "APPROVE_DESK_FINDING": "DESK_APPROVED",
            "ROUTE_TO_FORMAL_AUDIT": "FORMAL_AUDIT_ROUTE",
            "REQUIRE_PROFESSIONAL_REVIEW": "PROFESSIONAL_REVIEW",
        }[decision]
        self.conn.execute("UPDATE findings SET review_status=? WHERE id=?", (review_status, finding_id))
        self.repo._audit(org_id, reviewer_id, "REVIEW", "Finding", finding_id, {
            "review_id": review_id,
            "reviewer_role": reviewer_role,
            "decision": decision,
            "rationale": rationale,
        })
        self.conn.commit()
        return {
            "id": review_id,
            "finding_id": finding_id,
            "reviewer_id": reviewer_id,
            "reviewer_role": reviewer_role,
            "decision": decision,
            "rationale": rationale,
            "reviewed_at": reviewed_at,
            "claim_ready": False,
        }

    def recoverability_register(self, org_id: str) -> list[dict[str, Any]]:
        self.repo._require_org(org_id)
        rows = self.conn.execute(
            """SELECT
                   f.id AS finding_id,
                   f.agreement_id,
                   a.title AS agreement_title,
                   e.legal_name AS licensee_name,
                   f.finding_type,
                   f.state,
                   f.confidence,
                   f.amount_decimal,
                   f.currency,
                   f.review_status,
                   f.created_at
               FROM findings f
               JOIN agreements a ON a.id=f.agreement_id
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE l.organization_id=? AND e.organization_id=?
               ORDER BY f.created_at DESC, f.id DESC""",
            (org_id, org_id),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["claim_ready"] = False
            item["amount_label"] = "ANALYTICAL_CANDIDATE" if item["state"] == FindingState.RECOVERY_CANDIDATE.value and item["amount_decimal"] is not None else None
            result.append(item)
        return result

    def register_summary(self, org_id: str) -> dict[str, Any]:
        items = self.recoverability_register(org_id)
        states: dict[str, int] = {}
        supported_candidate_total = Decimal("0")
        currencies = set()
        for item in items:
            states[item["state"]] = states.get(item["state"], 0) + 1
            if item["amount_label"] == "ANALYTICAL_CANDIDATE" and item["amount_decimal"] is not None:
                currencies.add(item["currency"])
                supported_candidate_total += Decimal(item["amount_decimal"])
        total_value: Optional[str] = None
        total_currency: Optional[str] = None
        if len(currencies) == 1:
            total_value = format(supported_candidate_total, "f")
            total_currency = next(iter(currencies))
        return {
            "finding_count": len(items),
            "states": states,
            "analytical_candidate_total": total_value,
            "analytical_candidate_currency": total_currency,
            "mixed_currency_total_suppressed": len(currencies) > 1,
            "claim_ready_count": 0,
        }
