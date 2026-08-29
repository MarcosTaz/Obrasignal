from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Tuple

from recoverability_scan import ScanState
from royalty_engine import FindingState, PeriodInput, RoyaltyRule
from service_pipeline import EvidencePack, RecoverabilityCase, run_case


@dataclass(frozen=True)
class PortfolioRun:
    packs: Tuple[EvidencePack, ...]

    def count_calculation_state(self, state: FindingState) -> int:
        return sum(1 for pack in self.packs if pack.calculation.state == state)

    def count_scan_state(self, state: ScanState) -> int:
        return sum(1 for pack in self.packs if pack.scan.state == state)

    @property
    def claimed_cases(self) -> int:
        return sum(1 for pack in self.packs if pack.claim_ready)


def _case(
    index: int,
    *,
    gross_sales: Decimal,
    reported: Decimal,
    paid: Decimal,
    today: date,
    source_complete: bool = True,
    contract_complete: bool = True,
    auditor_requirement: str | None = None,
    professional_review: bool = False,
    duplicate_transactions: bool = False,
    audit_right_supported: bool | None = True,
) -> RecoverabilityCase:
    return RecoverabilityCase(
        case_id=f"TTO-CASE-{index:03d}",
        licensee_id=f"LICENSEE-{index:03d}",
        agreement_id=f"AGR-{index:03d}",
        annual_reported_royalty=reported * Decimal("4"),
        audit_deadline=today + timedelta(days=30 + (index % 300)),
        audit_right_supported=audit_right_supported,
        contract_version_complete=contract_complete,
        auditor_requirement=auditor_requirement,
        rule=RoyaltyRule(
            rule_id=f"RULE-{index:03d}",
            basis="PERCENTAGE_NET_SALES",
            rate=Decimal("0.05"),
            source_clause=f"Agreement {index:03d} section 4.2",
            requires_professional_review=professional_review,
        ),
        period_input=PeriodInput(
            gross_sales=gross_sales,
            permitted_deductions=Decimal("10000"),
            reported_royalty=reported,
            paid_royalty=paid,
            source_data_complete=source_complete,
            duplicate_transactions_detected=duplicate_transactions,
        ),
    )


def generate_tto_portfolio(today: date) -> Tuple[RecoverabilityCase, ...]:
    cases = []
    index = 1

    # 100 correct-reporting controls: expected = reported = paid = 4,500.
    for _ in range(100):
        cases.append(_case(index, gross_sales=Decimal("100000"), reported=Decimal("4500"), paid=Decimal("4500"), today=today))
        index += 1

    # 20 supported desk-review candidates: expected 5,500; paid 4,500.
    for _ in range(20):
        cases.append(_case(index, gross_sales=Decimal("120000"), reported=Decimal("4500"), paid=Decimal("4500"), today=today))
        index += 1

    # 10 supported candidates that contractually require a formal auditor.
    for _ in range(10):
        cases.append(_case(index, gross_sales=Decimal("120000"), reported=Decimal("4500"), paid=Decimal("4500"), today=today, auditor_requirement="Independent CPA"))
        index += 1

    # 15 missing-data traps. They must never produce a money candidate.
    for _ in range(15):
        cases.append(_case(index, gross_sales=Decimal("120000"), reported=Decimal("4500"), paid=Decimal("4500"), today=today, source_complete=False))
        index += 1

    # 10 incomplete operative-contract-version traps.
    for _ in range(10):
        cases.append(_case(index, gross_sales=Decimal("120000"), reported=Decimal("4500"), paid=Decimal("4500"), today=today, contract_complete=False))
        index += 1

    # 5 contract/accounting-judgment traps.
    for _ in range(5):
        cases.append(_case(index, gross_sales=Decimal("120000"), reported=Decimal("4500"), paid=Decimal("4500"), today=today, professional_review=True))
        index += 1

    # 5 duplicate-transaction traps.
    for _ in range(5):
        cases.append(_case(index, gross_sales=Decimal("120000"), reported=Decimal("4500"), paid=Decimal("4500"), today=today, duplicate_transactions=True))
        index += 1

    # 5 unknown-audit-right cases. Calculation may exist, but audit entitlement is not inferred.
    for _ in range(5):
        cases.append(_case(index, gross_sales=Decimal("120000"), reported=Decimal("4500"), paid=Decimal("4500"), today=today, audit_right_supported=None))
        index += 1

    if len(cases) != 170:
        raise AssertionError(f"synthetic portfolio must contain exactly 170 cases, got {len(cases)}")
    return tuple(cases)


def run_tto_portfolio(today: date, cases: Iterable[RecoverabilityCase] | None = None) -> PortfolioRun:
    source = tuple(cases) if cases is not None else generate_tto_portfolio(today)
    return PortfolioRun(tuple(run_case(case, today) for case in source))
