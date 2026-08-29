from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Optional

from repository import NotFoundError, RoyaltyRepository


SUPPORTED_RULE_BASES = {
    "PERCENTAGE_GROSS_SALES",
    "PERCENTAGE_NET_SALES",
    "PER_UNIT",
    "TIERED_NET_SALES",
    "SUBLICENSE_SHARE",
}
REVIEW_STATES = {"UNREVIEWED", "REVIEWED", "HUMAN_REVIEWED", "APPROVED", "REJECTED"}


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _required(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _review_state(value: str) -> str:
    state = _required(value, "review_status").upper()
    if state not in REVIEW_STATES:
        raise ValueError("unsupported review status")
    return state


def _decimal_text(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    if not value.is_finite() or value < 0:
        raise ValueError("royalty numeric fields must be finite and non-negative")
    return format(value, "f")


class ContractStore:
    def __init__(self, repository: RoyaltyRepository):
        self.repo = repository
        self.conn = repository.conn

    def add_clause(
        self,
        org_id: str,
        agreement_version_id: str,
        clause_ref: str,
        clause_type: str,
        actor_id: str,
        *,
        text_excerpt: Optional[str] = None,
        evidence_id: Optional[str] = None,
        review_status: str = "UNREVIEWED",
    ) -> dict[str, Any]:
        self.repo.get_agreement_version(org_id, agreement_version_id)
        clause_ref = _required(clause_ref, "clause_ref")
        clause_type = _required(clause_type, "clause_type")
        review_status = _review_state(review_status)
        if evidence_id is not None:
            self.repo.get_evidence(org_id, evidence_id)
        excerpt = text_excerpt.strip() if isinstance(text_excerpt, str) and text_excerpt.strip() else None
        if excerpt is not None and len(excerpt) > 2000:
            raise ValueError("text_excerpt exceeds 2000 characters")
        clause_id = _id("clause")
        self.conn.execute(
            """INSERT INTO clauses(id, agreement_version_id, clause_ref, clause_type, text_excerpt, evidence_id, review_status)
               VALUES(?,?,?,?,?,?,?)""",
            (clause_id, agreement_version_id, clause_ref, clause_type, excerpt, evidence_id, review_status),
        )
        version = self.repo.get_agreement_version(org_id, agreement_version_id)
        self.repo._audit(org_id, actor_id, "CREATE", "Clause", clause_id, {
            "agreement_id": version["agreement_id"],
            "agreement_version_id": agreement_version_id,
            "clause_ref": clause_ref,
            "clause_type": clause_type,
            "evidence_id": evidence_id,
            "review_status": review_status,
        })
        self.conn.commit()
        return self.get_clause(org_id, clause_id)

    def get_clause(self, org_id: str, clause_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT c.* FROM clauses c
               JOIN agreement_versions v ON v.id=c.agreement_version_id
               JOIN agreements a ON a.id=v.agreement_id
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE c.id=? AND l.organization_id=? AND e.organization_id=?""",
            (clause_id, org_id, org_id),
        ).fetchone()
        if not row:
            raise NotFoundError("clause not found in organization scope")
        return dict(row)

    def set_clause_review_status(self, org_id: str, clause_id: str, review_status: str, actor_id: str, rationale: str) -> dict[str, Any]:
        clause = self.get_clause(org_id, clause_id)
        status = _review_state(review_status)
        rationale = _required(rationale, "rationale")
        if status in {"UNREVIEWED", "HUMAN_REVIEWED", "APPROVED"}:
            raise ValueError("review transition must use REVIEWED or REJECTED")
        self.conn.execute("UPDATE clauses SET review_status=? WHERE id=?", (status, clause_id))
        self.repo._audit(org_id, actor_id, "REVIEW", "Clause", clause_id, {
            "previous_status": clause["review_status"], "review_status": status, "rationale": rationale,
        })
        self.conn.commit()
        return self.get_clause(org_id, clause_id)

    def add_royalty_rule(
        self,
        org_id: str,
        agreement_version_id: str,
        clause_id: str,
        basis: str,
        currency: str,
        actor_id: str,
        *,
        rate: Optional[Decimal] = None,
        per_unit: Optional[Decimal] = None,
        minimum_guarantee: Optional[Decimal] = None,
        cap: Optional[Decimal] = None,
        floor: Optional[Decimal] = None,
        effective_from: Optional[str] = None,
        effective_to: Optional[str] = None,
        review_status: str = "UNREVIEWED",
    ) -> dict[str, Any]:
        version = self.repo.get_agreement_version(org_id, agreement_version_id)
        clause = self.get_clause(org_id, clause_id)
        if clause["agreement_version_id"] != agreement_version_id:
            raise ValueError("clause does not belong to supplied agreement version")
        basis = _required(basis, "basis").upper()
        if basis not in SUPPORTED_RULE_BASES:
            raise ValueError("unsupported deterministic royalty basis")
        currency = _required(currency, "currency").upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        review_status = _review_state(review_status)
        if effective_from and effective_to and effective_to < effective_from:
            raise ValueError("effective_to must not precede effective_from")
        rate_text = _decimal_text(rate)
        per_unit_text = _decimal_text(per_unit)
        minimum_text = _decimal_text(minimum_guarantee)
        cap_text = _decimal_text(cap)
        floor_text = _decimal_text(floor)
        if basis in {"PERCENTAGE_GROSS_SALES", "PERCENTAGE_NET_SALES"} and rate_text is None:
            raise ValueError("percentage royalty basis requires rate")
        if basis == "PER_UNIT" and per_unit_text is None:
            raise ValueError("per-unit basis requires per_unit")
        if cap is not None and floor is not None and cap < floor:
            raise ValueError("cap must not be below floor")
        rule_id = _id("rule")
        self.conn.execute(
            """INSERT INTO royalty_rules(
                   id, agreement_version_id, clause_id, basis, rate_decimal, per_unit_decimal,
                   minimum_guarantee_decimal, cap_decimal, floor_decimal, currency,
                   effective_from, effective_to, review_status
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rule_id, agreement_version_id, clause_id, basis, rate_text, per_unit_text,
                minimum_text, cap_text, floor_text, currency, effective_from, effective_to, review_status,
            ),
        )
        self.repo._audit(org_id, actor_id, "CREATE", "RoyaltyRule", rule_id, {
            "agreement_id": version["agreement_id"],
            "agreement_version_id": agreement_version_id,
            "clause_id": clause_id,
            "basis": basis,
            "currency": currency,
            "review_status": review_status,
        })
        self.conn.commit()
        return self.get_royalty_rule(org_id, rule_id)

    def get_royalty_rule(self, org_id: str, rule_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT r.* FROM royalty_rules r
               JOIN agreement_versions v ON v.id=r.agreement_version_id
               JOIN agreements a ON a.id=v.agreement_id
               JOIN licensors l ON l.id=a.licensor_id
               JOIN licensees e ON e.id=a.licensee_id
               WHERE r.id=? AND l.organization_id=? AND e.organization_id=?""",
            (rule_id, org_id, org_id),
        ).fetchone()
        if not row:
            raise NotFoundError("royalty rule not found in organization scope")
        return dict(row)

    def set_rule_review_status(self, org_id: str, rule_id: str, review_status: str, actor_id: str, rationale: str) -> dict[str, Any]:
        rule = self.get_royalty_rule(org_id, rule_id)
        status = _review_state(review_status)
        rationale = _required(rationale, "rationale")
        if status in {"UNREVIEWED", "HUMAN_REVIEWED", "APPROVED"}:
            raise ValueError("review transition must use REVIEWED or REJECTED")
        clause = self.get_clause(org_id, rule["clause_id"])
        if status == "REVIEWED" and clause["review_status"] != "REVIEWED":
            raise ValueError("royalty rule cannot be reviewed until its source clause is reviewed")
        self.conn.execute("UPDATE royalty_rules SET review_status=? WHERE id=?", (status, rule_id))
        self.repo._audit(org_id, actor_id, "REVIEW", "RoyaltyRule", rule_id, {
            "previous_status": rule["review_status"], "review_status": status, "rationale": rationale,
        })
        self.conn.commit()
        return self.get_royalty_rule(org_id, rule_id)

    def list_rules_for_agreement_version(self, org_id: str, agreement_version_id: str) -> list[dict[str, Any]]:
        self.repo.get_agreement_version(org_id, agreement_version_id)
        rows = self.conn.execute(
            "SELECT id FROM royalty_rules WHERE agreement_version_id=? ORDER BY id",
            (agreement_version_id,),
        ).fetchall()
        return [self.get_royalty_rule(org_id, row["id"]) for row in rows]
