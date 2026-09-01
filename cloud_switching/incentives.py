from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Sequence

Money = Decimal


class IncentiveStatus(str, Enum):
    POTENTIAL = "potential"
    APPROVED = "approved"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    EXPIRED = "expired"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Incentive:
    incentive_id: str
    program: str
    status: IncentiveStatus
    potential_amount: Optional[Money] = None
    approved_amount: Optional[Money] = None
    received_amount: Optional[Money] = None
    cap_amount: Optional[Money] = None
    expiry: Optional[date] = None
    eligibility_evidence_id: Optional[str] = None
    approval_evidence_id: Optional[str] = None
    receipt_evidence_id: Optional[str] = None

    def validate(self) -> None:
        if not self.incentive_id.strip() or not self.program.strip():
            raise ValueError("incentive id and program are required")
        values = (self.potential_amount, self.approved_amount, self.received_amount, self.cap_amount)
        if any(value is not None and value < 0 for value in values):
            raise ValueError("incentive amounts cannot be negative")
        if self.cap_amount is not None:
            for value in (self.potential_amount, self.approved_amount, self.received_amount):
                if value is not None and value > self.cap_amount:
                    raise ValueError("incentive amount cannot exceed cap")
        if self.received_amount is not None:
            if self.approved_amount is None:
                raise ValueError("received incentive requires approved amount")
            if self.received_amount > self.approved_amount:
                raise ValueError("received incentive cannot exceed approved amount")
        if self.status in {IncentiveStatus.APPROVED, IncentiveStatus.PARTIALLY_RECEIVED, IncentiveStatus.RECEIVED}:
            if self.approved_amount is None or not self.approval_evidence_id:
                raise ValueError("approved incentive requires amount and approval evidence")
        if self.status in {IncentiveStatus.PARTIALLY_RECEIVED, IncentiveStatus.RECEIVED}:
            if self.received_amount is None or not self.receipt_evidence_id:
                raise ValueError("received incentive requires receipt evidence")
        if self.status is IncentiveStatus.RECEIVED and self.received_amount != self.approved_amount:
            raise ValueError("received status requires full approved amount to be received")
        if self.status is IncentiveStatus.PARTIALLY_RECEIVED:
            if self.received_amount is None or self.received_amount <= 0:
                raise ValueError("partial receipt requires positive received amount")
            if self.approved_amount is None or self.received_amount >= self.approved_amount:
                raise ValueError("partial receipt must be below approved amount")
        if self.status is IncentiveStatus.EXPIRED and (self.received_amount or Decimal("0")) > 0:
            raise ValueError("expired uncaptured incentive cannot carry received value")

    def captured_value(self) -> Money:
        self.validate()
        if self.status not in {IncentiveStatus.PARTIALLY_RECEIVED, IncentiveStatus.RECEIVED}:
            return Decimal("0")
        return self.received_amount or Decimal("0")


def total_captured_value(incentives: Sequence[Incentive]) -> Money:
    seen = set()
    total = Decimal("0")
    for incentive in incentives:
        if incentive.incentive_id in seen:
            raise ValueError(f"duplicate incentive id: {incentive.incentive_id}")
        seen.add(incentive.incentive_id)
        total += incentive.captured_value()
    return total
