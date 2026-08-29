from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from contract_store import ContractStore
from finding_store import FindingStore
from repository import NotFoundError, RoyaltyRepository
from royalty_engine import FindingState


@dataclass(frozen=True)
class FormalAuditPacket:
    finding_id: str
    agreement: dict[str, Any]
    agreement_version: dict[str, Any]
    source_clause: dict[str, Any]
    royalty_rule: dict[str, Any]
    calculation_run: dict[str, Any]
    evidence: tuple[dict[str, Any], ...]
    analytical_candidate_amount: str | None
    currency: str | None
    review_status: str
    auditor_engaged: bool = False
    claim_ready: bool = False


def _link_payload(repository: RoyaltyRepository, org_id: str, finding_id: str) -> dict[str, Any]:
    rows = repository.conn.execute(
        """SELECT payload_json FROM audit_events
           WHERE organization_id=? AND entity_type='Finding' AND entity_id=? AND event_type='LINK'
           ORDER BY event_at DESC, id DESC""",
        (org_id, finding_id),
    ).fetchall()
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            continue
        if payload.get("calculation_run_id") and payload.get("rule_id"):
            return payload
    raise NotFoundError("finding calculation lineage not found")


def build_formal_audit_packet(repository: RoyaltyRepository, org_id: str, finding_id: str) -> FormalAuditPacket:
    findings = FindingStore(repository)
    contracts = ContractStore(repository)
    finding = findings.get_finding(org_id, finding_id)
    if finding["state"] != FindingState.RECOVERY_CANDIDATE.value:
        raise ValueError("only a RECOVERY_CANDIDATE can be routed to formal audit")
    if finding["review_status"] != "FORMAL_AUDIT_ROUTE":
        raise ValueError("finding must be explicitly routed to formal audit by a reviewer")

    agreement = repository.get_agreement(org_id, finding["agreement_id"])
    link = _link_payload(repository, org_id, finding_id)
    calculation_run = repository.get_calculation_run(org_id, link["calculation_run_id"])
    if calculation_run["agreement_id"] != agreement["id"]:
        raise ValueError("calculation lineage does not match finding agreement")
    agreement_version = repository.get_agreement_version(org_id, calculation_run["agreement_version_id"])
    rule = contracts.get_royalty_rule(org_id, link["rule_id"])
    if rule["agreement_version_id"] != agreement_version["id"]:
        raise ValueError("royalty rule lineage does not match calculation agreement version")
    clause = contracts.get_clause(org_id, rule["clause_id"])
    if finding["source_clause_id"] != clause["id"]:
        raise ValueError("finding source clause does not match royalty rule lineage")

    evidence_rows = repository.conn.execute(
        """SELECT e.id FROM finding_evidence fe
           JOIN evidence e ON e.id=fe.evidence_id
           WHERE fe.finding_id=? AND e.organization_id=?
           ORDER BY e.id""",
        (finding_id, org_id),
    ).fetchall()
    evidence = tuple(repository.get_evidence(org_id, row["id"]) for row in evidence_rows)
    if not evidence:
        raise ValueError("formal audit packet requires persisted finding evidence")

    return FormalAuditPacket(
        finding_id=finding_id,
        agreement=agreement,
        agreement_version=agreement_version,
        source_clause=clause,
        royalty_rule=rule,
        calculation_run=calculation_run,
        evidence=evidence,
        analytical_candidate_amount=finding["amount_decimal"],
        currency=finding["currency"],
        review_status=finding["review_status"],
        auditor_engaged=False,
        claim_ready=False,
    )


def packet_to_dict(packet: FormalAuditPacket) -> dict[str, Any]:
    return {
        "finding_id": packet.finding_id,
        "agreement": packet.agreement,
        "agreement_version": packet.agreement_version,
        "source_clause": packet.source_clause,
        "royalty_rule": packet.royalty_rule,
        "calculation_run": packet.calculation_run,
        "evidence": list(packet.evidence),
        "analytical_candidate_amount": packet.analytical_candidate_amount,
        "currency": packet.currency,
        "review_status": packet.review_status,
        "auditor_engaged": False,
        "claim_ready": False,
        "disclaimer": "Handoff packet only. It does not assert an audit entitlement, debt, claim, auditor acceptance, or recovery.",
    }
