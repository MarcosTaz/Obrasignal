from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Iterable, Optional, Tuple

from risk_catalog import UC_2023_SOURCE, validate_risk_factors
from royalty_engine import DeadlineState, FindingState, assess_deadline


class ScanState(str, Enum):
    READY_FOR_DESK_REVIEW = "READY_FOR_DESK_REVIEW"
    FORMAL_AUDIT_CANDIDATE = "FORMAL_AUDIT_CANDIDATE"
    NEEDS_DATA = "NEEDS_DATA"
    PROFESSIONAL_REVIEW = "PROFESSIONAL_REVIEW"
    NO_CURRENT_RECOVERY_SIGNAL = "NO_CURRENT_RECOVERY_SIGNAL"


@dataclass(frozen=True)
class LicenseeSignal:
    licensee_id: str
    annual_reported_royalty: Optional[Decimal]
    finding_state: FindingState
    supported_variance: Optional[Decimal]
    audit_deadline: Optional[date]
    audit_right_supported: Optional[bool]
    source_data_complete: bool
    contract_version_complete: bool
    auditor_requirement: Optional[str] = None
    missing_items: Tuple[str, ...] = ()
    risk_factors: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanResult:
    licensee_id: str
    state: ScanState
    priority_score: int
    deadline_state: DeadlineState
    supported_variance: Optional[Decimal]
    rationale: Tuple[str, ...]
    missing_items: Tuple[str, ...]
    formal_auditor_required: bool
    unweighted_risk_factors: Tuple[str, ...] = ()
    risk_factor_source: Optional[str] = None


def _score_deadline(state: DeadlineState) -> int:
    return {
        DeadlineState.APPROACHING: 40,
        DeadlineState.SAFE: 10,
        DeadlineState.UNKNOWN: 0,
        DeadlineState.EXPIRED: -50,
    }[state]


def scan_licensee(signal: LicenseeSignal, today: date, approaching_days: int = 120) -> ScanResult:
    deadline = assess_deadline(today, signal.audit_deadline, approaching_days)
    reasons = []
    missing = list(signal.missing_items)
    score = _score_deadline(deadline.state)
    formal_required = bool((signal.auditor_requirement or "").strip())
    risk_factors = validate_risk_factors(signal.risk_factors)

    if signal.audit_right_supported is None:
        missing.append("contract-supported audit-right determination")
        reasons.append("Audit right is unknown; no formal audit entitlement is assumed.")
    elif signal.audit_right_supported is False:
        reasons.append("No supported contractual audit right is currently evidenced.")
        score -= 25
    else:
        reasons.append("Contractual audit right is evidenced.")
        score += 15

    if not signal.contract_version_complete:
        missing.append("complete operative agreement/amendment set")
        reasons.append("Operative contract version is incomplete.")
        score -= 30

    if not signal.source_data_complete:
        missing.append("complete sales/usage/statement/payment evidence")
        reasons.append("Source data is incomplete.")
        score -= 20

    if deadline.state == DeadlineState.APPROACHING:
        reasons.append("Supported audit/lookback deadline is approaching.")
    elif deadline.state == DeadlineState.UNKNOWN:
        reasons.append("No supported audit/lookback deadline is available.")
    elif deadline.state == DeadlineState.EXPIRED:
        reasons.append("Supplied deadline has passed; recoverability requires professional review and is not assumed lost.")

    if signal.finding_state == FindingState.RECOVERY_CANDIDATE and signal.supported_variance is not None and signal.supported_variance > 0:
        score += 35
        reasons.append("A positive deterministic variance is supported by current contract/data inputs.")
    elif signal.finding_state == FindingState.NO_DEFENSIBLE_RECOVERY:
        reasons.append("Current supported inputs show no positive recoverable difference.")
        score -= 10
    elif signal.finding_state in {FindingState.UNKNOWN, FindingState.NEEDS_DATA}:
        reasons.append("Calculation is unresolved because evidence is missing or insufficient.")
        score -= 10
    elif signal.finding_state == FindingState.REQUIRES_PROFESSIONAL_REVIEW:
        reasons.append("Calculation depends on professional contract/accounting judgment.")

    if signal.annual_reported_royalty is not None:
        if signal.annual_reported_royalty >= Decimal("1000000"):
            score += 10
        elif signal.annual_reported_royalty >= Decimal("250000"):
            score += 5
    else:
        missing.append("annual royalty stream value")

    if risk_factors:
        reasons.append(
            f"{len(risk_factors)} externally sourced qualitative risk factor(s) recorded; they are deliberately unweighted and do not alter the numeric priority score."
        )

    score = max(0, min(100, score))

    if signal.finding_state == FindingState.REQUIRES_PROFESSIONAL_REVIEW or deadline.state == DeadlineState.EXPIRED:
        state = ScanState.PROFESSIONAL_REVIEW
    elif missing or signal.finding_state in {FindingState.UNKNOWN, FindingState.NEEDS_DATA}:
        state = ScanState.NEEDS_DATA
    elif signal.finding_state == FindingState.NO_DEFENSIBLE_RECOVERY:
        state = ScanState.NO_CURRENT_RECOVERY_SIGNAL
    elif (
        signal.finding_state == FindingState.RECOVERY_CANDIDATE
        and signal.audit_right_supported is True
        and signal.contract_version_complete
        and signal.source_data_complete
    ):
        state = ScanState.FORMAL_AUDIT_CANDIDATE if formal_required else ScanState.READY_FOR_DESK_REVIEW
    else:
        state = ScanState.READY_FOR_DESK_REVIEW

    return ScanResult(
        licensee_id=signal.licensee_id,
        state=state,
        priority_score=score,
        deadline_state=deadline.state,
        supported_variance=signal.supported_variance,
        rationale=tuple(reasons),
        missing_items=tuple(dict.fromkeys(missing)),
        formal_auditor_required=formal_required,
        unweighted_risk_factors=risk_factors,
        risk_factor_source=UC_2023_SOURCE if risk_factors else None,
    )


def rank_portfolio(signals: Iterable[LicenseeSignal], today: date, approaching_days: int = 120) -> Tuple[ScanResult, ...]:
    results = [scan_licensee(signal, today=today, approaching_days=approaching_days) for signal in signals]
    return tuple(sorted(results, key=lambda item: (-item.priority_score, item.licensee_id)))
