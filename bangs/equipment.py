from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .costs import CostAssessment, CostBasis, CostLine, assess_cost_lines
from .evidence import Availability, SourceEvidence
from .money import Money, as_decimal

class EquipmentMode(str, Enum):
    RENT = "RENT"
    BUY = "BUY"

class RentalRateBasis(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"

@dataclass(frozen=True, slots=True)
class EquipmentOption:
    option_id: str
    equipment_type: str
    mode: EquipmentMode
    quantity: int
    rate: Money
    rate_basis: RentalRateBasis | None
    periods: Decimal
    availability: Availability
    evidence: SourceEvidence
    required_capacity: str | None = None
    deposit: Money | None = None
    transport: Money | None = None
    operator: Money | None = None
    insurance: Money | None = None
    fuel: Money | None = None
    supplier_id: str | None = None

    def __post_init__(self) -> None:
        option_id = str(self.option_id or "").strip()
        equipment_type = str(self.equipment_type or "").strip()
        if not option_id or len(option_id) > 180 or not equipment_type or len(equipment_type) > 300:
            raise ValueError("equipment option id and type are required and bounded")
        if self.required_capacity is not None and len(str(self.required_capacity)) > 500:
            raise ValueError("required capacity too long")
        if self.supplier_id is not None and len(str(self.supplier_id)) > 180:
            raise ValueError("supplier_id too long")
        object.__setattr__(self, "option_id", option_id)
        object.__setattr__(self, "equipment_type", equipment_type)
        if self.quantity <= 0:
            raise ValueError("equipment quantity must be positive")
        periods = as_decimal(self.periods)
        if periods <= 0:
            raise ValueError("equipment periods must be positive")
        if self.mode is EquipmentMode.RENT and self.rate_basis is None:
            raise ValueError("rental option requires rate_basis")
        if self.mode is EquipmentMode.BUY and self.rate_basis is not None:
            raise ValueError("buy option must not carry rental rate basis")
        object.__setattr__(self, "periods", periods)

@dataclass(frozen=True, slots=True)
class EquipmentAssessment:
    option_id: str
    economic: CostAssessment
    cash_outlay: CostAssessment
    deposit: Money | None
    availability: Availability


def assess_equipment(option: EquipmentOption) -> EquipmentAssessment:
    multiplier = option.periods if option.mode is EquipmentMode.RENT else Decimal("1")
    base = option.rate.times(multiplier * option.quantity)
    lines = [CostLine("equipment_rate", base, CostBasis.MARKET_OBSERVATION, option.evidence)]
    for code, amount in (
        ("equipment_transport", option.transport),
        ("operator", option.operator),
        ("insurance", option.insurance),
        ("fuel", option.fuel),
    ):
        if amount is not None:
            lines.append(CostLine(code, amount, CostBasis.ESTIMATE, option.evidence))
    warnings = []
    if option.availability is Availability.UNAVAILABLE:
        warnings.append("OPTION_UNAVAILABLE")
    elif option.availability is Availability.UNKNOWN:
        warnings.append("AVAILABILITY_UNKNOWN")
    economic = assess_cost_lines(lines, warnings=warnings)
    cash_lines = list(lines)
    if option.deposit is not None:
        cash_lines.append(CostLine("deposit", option.deposit, CostBasis.FACT, option.evidence, cash_only=True))
    cash = assess_cost_lines(cash_lines, warnings=warnings)
    return EquipmentAssessment(option.option_id, economic, cash, option.deposit, option.availability)
