from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class OracleTruth:
    scenario_id: str
    true_recoverable: Decimal
    true_not_yet_due: Decimal
    true_disputed: Decimal
    expected_categories: tuple[str, ...]


SCENARIOS = {
    "zero_recovery": OracleTruth(
        scenario_id="zero_recovery",
        true_recoverable=Decimal("0"),
        true_not_yet_due=Decimal("25000"),
        true_disputed=Decimal("0"),
        expected_categories=(),
    ),
    "matured_retention": OracleTruth(
        scenario_id="matured_retention",
        true_recoverable=Decimal("50000"),
        true_not_yet_due=Decimal("0"),
        true_disputed=Decimal("0"),
        expected_categories=("RETENTION_MATURED_UNRELEASED",),
    ),
    "certified_not_invoiced": OracleTruth(
        scenario_id="certified_not_invoiced",
        true_recoverable=Decimal("30000"),
        true_not_yet_due=Decimal("0"),
        true_disputed=Decimal("0"),
        expected_categories=("CERTIFIED_NOT_INVOICED",),
    ),
}
