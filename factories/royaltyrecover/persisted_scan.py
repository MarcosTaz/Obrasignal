from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Iterable, Optional

from contract_store import ContractStore
from finding_store import FindingStore
from repository import RoyaltyRepository
from royalty_engine import ENGINE_VERSION, FindingState, PeriodInput, RoyaltyRule, calculate


REVIEWED_RULE_STATUSES = {"REVIEWED", "HUMAN_REVIEWED", "APPROVED"}


@dataclass(frozen=True)
class PersistedScanResult:
    calculation_run: dict[str, Any]
    calculation_state: FindingState
    expected_royalty: Optional[Decimal]
    recoverable_candidate: Optional[Decimal]
    finding: dict[str, Any]
    claim_ready: bool = False


def _decimal(value: Optional[str]) -> Optional[Decimal]:
    return None if value is None else Decimal(value)


def _period_payload(data: PeriodInput) -> dict[str, Any]:
    result = {}
    for key, value in asdict(data).items():
        if isinstance(value, Decimal):
            result[key] = format(value, "f")
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _engine_rule(stored_rule: dict[str, Any], clause: dict[str, Any]) -> RoyaltyRule:
    return RoyaltyRule(
        rule_id=stored_rule["id"],
        basis=stored_rule["basis"],
        rate=_decimal(stored_rule["rate_decimal"]),
        per_unit=_decimal(stored_rule["per_unit_decimal"]),
        minimum_guarantee=_decimal(stored_rule["minimum_guarantee_decimal"]),
        cap=_decimal(stored_rule["cap_decimal"]),
        floor=_decimal(stored_rule["floor_decimal"]),
        currency=stored_rule["currency"],
        source_clause=clause["clause_ref"],
        requires_professional_review=False,
    )


def run_persisted_scan(
    repository: RoyaltyRepository,
    org_id: str,
    agreement_id: str,
    agreement_version_id: str,
    rule_id: str,
    period_start: str,
    period_end: str,
    period_input: PeriodInput,
    evidence_ids: Iterable[str],
    actor_id: str,
) -> PersistedScanResult:
    contract_store = ContractStore(repository)
    finding_store = FindingStore(repository)

    agreement = repository.get_agreement(org_id, agreement_id)
    version = repository.get_agreement_version(org_id, agreement_version_id)
    if version["agreement_id"] != agreement["id"]:
        raise ValueError("agreement version does not belong to supplied agreement")

    stored_rule = contract_store.get_royalty_rule(org_id, rule_id)
    if stored_rule["agreement_version_id"] != agreement_version_id:
        raise ValueError("royalty rule does not belong to supplied agreement version")
    clause = contract_store.get_clause(org_id, stored_rule["clause_id"])

    if str(clause["review_status"]).upper() not in REVIEWED_RULE_STATUSES:
        raise ValueError("source clause must be reviewed before deterministic calculation")
    if str(stored_rule["review_status"]).upper() not in REVIEWED_RULE_STATUSES:
        raise ValueError("royalty rule must be reviewed before deterministic calculation")

    evidence = []
    for evidence_id in tuple(dict.fromkeys(evidence_ids)):
        evidence.append(repository.get_evidence(org_id, evidence_id))
    if not evidence:
        raise ValueError("at least one tenant-scoped source evidence record is required")

    input_payload = {
        "agreement_version_sha256": version["document_sha256"],
        "rule_id": stored_rule["id"],
        "rule_basis": stored_rule["basis"],
        "rule_review_status": stored_rule["review_status"],
        "clause_id": clause["id"],
        "clause_ref": clause["clause_ref"],
        "clause_review_status": clause["review_status"],
        "evidence": sorted(
            ({"id": item["id"], "sha256": item["source_sha256"], "type": item["evidence_type"]} for item in evidence),
            key=lambda item: item["id"],
        ),
        "period_input": _period_payload(period_input),
    }
    calculation_run = repository.create_calculation_run(
        org_id,
        agreement_id,
        agreement_version_id,
        period_start,
        period_end,
        ENGINE_VERSION,
        input_payload,
        actor_id,
    )

    result = calculate(_engine_rule(stored_rule, clause), period_input)
    confidence = {
        FindingState.RECOVERY_CANDIDATE: "SUPPORTED_DETERMINISTIC_ARITHMETIC",
        FindingState.NO_DEFENSIBLE_RECOVERY: "SUPPORTED_DETERMINISTIC_ARITHMETIC",
        FindingState.NEEDS_DATA: "INCOMPLETE_EVIDENCE",
        FindingState.UNKNOWN: "UNKNOWN",
        FindingState.REQUIRES_PROFESSIONAL_REVIEW: "PROFESSIONAL_REVIEW_REQUIRED",
    }[result.state]
    finding = finding_store.create_finding(
        org_id,
        agreement_id,
        "PERSISTED_RULE_SCAN",
        result.state,
        confidence,
        actor_id,
        amount=result.recoverable_candidate,
        currency=stored_rule["currency"] if result.recoverable_candidate is not None else None,
        source_clause_id=clause["id"],
    )
    repository._audit(org_id, actor_id, "LINK", "Finding", finding["id"], {
        "calculation_run_id": calculation_run["id"],
        "rule_id": stored_rule["id"],
        "evidence_ids": [item["id"] for item in evidence],
    })
    repository.conn.commit()

    return PersistedScanResult(
        calculation_run=calculation_run,
        calculation_state=result.state,
        expected_royalty=result.expected_royalty,
        recoverable_candidate=result.recoverable_candidate,
        finding=finding,
        claim_ready=False,
    )
