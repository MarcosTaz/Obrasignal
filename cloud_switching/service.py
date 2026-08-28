from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Sequence

from .baseline import CurrentStateBaseline
from .decision import Decision, decide
from .domain import MigrationCase
from .incentives import Incentive, total_captured_value


@dataclass(frozen=True)
class DecisionPackage:
    company_id: str
    case_id: str
    decision: Decision
    reason: str
    baseline_annual_cost: Optional[Decimal]
    gross_switching_cost: Optional[Decimal]
    captured_incentives: Decimal
    customer_cash_switching_cost: Optional[Decimal]
    annual_status_quo_avoidance: Optional[Decimal]
    economic_payback_months: Optional[Decimal]
    customer_cash_payback_months: Optional[Decimal]
    unresolved_material_inputs: tuple[str, ...]
    audit_evidence_ids: tuple[str, ...]


def _audit_ids(baseline: CurrentStateBaseline, incentives: Sequence[Incentive]) -> tuple[str, ...]:
    ids = set()
    for component in baseline.components:
        if component.source_id:
            ids.add(component.source_id)
    for incentive in incentives:
        for source_id in (
            incentive.eligibility_evidence_id,
            incentive.approval_evidence_id,
            incentive.receipt_evidence_id,
        ):
            if source_id:
                ids.add(source_id)
    return tuple(sorted(ids))


def build_decision_package(
    baseline: CurrentStateBaseline,
    case: MigrationCase,
    incentives: Sequence[Incentive],
    *,
    maximum_payback_months: Decimal = Decimal("24"),
) -> DecisionPackage:
    captured = total_captured_value(incentives)
    case_received = case.provider_credit_received + case.partner_incentive_received
    if captured != case_received:
        raise ValueError(
            "incentive ledger does not reconcile to migration case received capital: "
            f"ledger={captured} case={case_received}"
        )

    decision = decide(
        baseline,
        case,
        maximum_payback_months=maximum_payback_months,
    )
    unresolved = baseline.unresolved_material_inputs()
    economics = decision.economics

    return DecisionPackage(
        company_id=baseline.company_id,
        case_id=case.case_id,
        decision=decision.decision,
        reason=decision.reason,
        baseline_annual_cost=decision.baseline_annual_cost,
        gross_switching_cost=None if economics is None else economics.gross_switching_cost,
        captured_incentives=captured,
        customer_cash_switching_cost=None if economics is None else economics.customer_cash_switching_cost,
        annual_status_quo_avoidance=None if economics is None else economics.annual_status_quo_avoidance,
        economic_payback_months=None if economics is None else economics.economic_payback_months,
        customer_cash_payback_months=None if economics is None else economics.customer_cash_payback_months,
        unresolved_material_inputs=unresolved,
        audit_evidence_ids=_audit_ids(baseline, incentives),
    )
