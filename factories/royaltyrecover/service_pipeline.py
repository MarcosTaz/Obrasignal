from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, Tuple

from recoverability_scan import LicenseeSignal, ScanResult, scan_licensee
from royalty_engine import CalculationResult, PeriodInput, RoyaltyRule, calculate


@dataclass(frozen=True)
class RecoverabilityCase:
    case_id: str
    licensee_id: str
    agreement_id: str
    annual_reported_royalty: Optional[Decimal]
    audit_deadline: Optional[date]
    audit_right_supported: Optional[bool]
    contract_version_complete: bool
    auditor_requirement: Optional[str]
    rule: RoyaltyRule
    period_input: PeriodInput


@dataclass(frozen=True)
class EvidencePack:
    case_id: str
    agreement_id: str
    licensee_id: str
    calculation: CalculationResult
    scan: ScanResult
    information_requests: Tuple[str, ...]
    claim_ready: bool
    claim_blocker: str


def _information_requests(case: RecoverabilityCase, calculation: CalculationResult, scan: ScanResult) -> Tuple[str, ...]:
    requests = list(scan.missing_items)
    if not case.rule.source_clause:
        requests.append("operative royalty clause and source location")
    if case.period_input.reported_royalty is None:
        requests.append("royalty statement for the tested period")
    if case.period_input.paid_royalty is None:
        requests.append("payment evidence for the tested period")
    if calculation.expected_royalty is None and not requests:
        requests.append("source evidence sufficient to reproduce the royalty calculation")
    return tuple(dict.fromkeys(requests))


def run_case(case: RecoverabilityCase, today: date) -> EvidencePack:
    calculation = calculate(case.rule, case.period_input)
    signal = LicenseeSignal(
        licensee_id=case.licensee_id,
        annual_reported_royalty=case.annual_reported_royalty,
        finding_state=calculation.state,
        supported_variance=calculation.recoverable_candidate,
        audit_deadline=case.audit_deadline,
        audit_right_supported=case.audit_right_supported,
        source_data_complete=case.period_input.source_data_complete,
        contract_version_complete=case.contract_version_complete,
        auditor_requirement=case.auditor_requirement,
    )
    scan = scan_licensee(signal, today=today)
    requests = _information_requests(case, calculation, scan)

    # A deterministic positive variance is never itself a claim. Real assertion
    # requires a human/professional review step outside this minimum pipeline.
    claim_ready = False
    if calculation.recoverable_candidate and calculation.recoverable_candidate > 0:
        blocker = "Positive variance is a recovery candidate only; human/professional review is required before assertion."
    else:
        blocker = "No supported positive recovery candidate is available for assertion."

    return EvidencePack(
        case_id=case.case_id,
        agreement_id=case.agreement_id,
        licensee_id=case.licensee_id,
        calculation=calculation,
        scan=scan,
        information_requests=requests,
        claim_ready=claim_ready,
        claim_blocker=blocker,
    )


def pack_to_dict(pack: EvidencePack) -> dict:
    data = asdict(pack)

    def normalize(value):
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, tuple):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if hasattr(value, "value"):
            return value.value
        return value

    return normalize(data)
