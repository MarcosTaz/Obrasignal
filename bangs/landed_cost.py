from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .costs import CostAssessment, CostBasis, CostLine, assess_cost_lines
from .evidence import TaxBasis
from .materials import MaterialPriceObservation, MaterialRequirement
from .money import Money, as_decimal
from .units import convert_quantity

@dataclass(frozen=True, slots=True)
class LandedCostAssessment:
    material_id: str
    purchase_quantity: Decimal
    purchase_unit: str
    assessment: CostAssessment
    waste_fraction: Decimal | None


def assess_landed_cost(
    requirement: MaterialRequirement,
    price: MaterialPriceObservation,
    *,
    delivery: CostLine | None = None,
    handling: CostLine | None = None,
    unloading: CostLine | None = None,
    known_tax: CostLine | None = None,
    known_duty: CostLine | None = None,
    waste_fraction: Decimal | int | str | float | None = None,
    other_costs: Iterable[CostLine] = (),
    cross_border: bool = False,
) -> LandedCostAssessment:
    if requirement.material_id != price.material_id:
        raise ValueError("material requirement and price observation do not match")
    if requirement.quantity is None or requirement.unit is None:
        return LandedCostAssessment(
            requirement.material_id,
            Decimal("0"),
            price.unit,
            assess_cost_lines((), unknown_components=("material_quantity",)),
            None,
        )
    required_in_price_unit = convert_quantity(requirement.quantity, requirement.unit, price.unit)
    purchase_quantity = required_in_price_unit
    if price.minimum_quantity is not None and price.minimum_quantity > purchase_quantity:
        purchase_quantity = price.minimum_quantity
    waste = None
    if waste_fraction is not None:
        waste = as_decimal(waste_fraction)
        if waste < 0 or waste > 1:
            raise ValueError("waste_fraction must be between 0 and 1")
        purchase_quantity *= Decimal("1") + waste
    purchase_basis = {
        "SUPPLIER_QUOTE": CostBasis.QUOTE,
        "LIVE_LIST_PRICE": CostBasis.MARKET_OBSERVATION,
        "OFFICIAL_CATALOGUE": CostBasis.MARKET_OBSERVATION,
        "MARKET_OBSERVATION": CostBasis.MARKET_OBSERVATION,
        "USER_INPUT": CostBasis.ASSUMPTION,
        "ESTIMATE": CostBasis.ESTIMATE,
        "HISTORICAL_PRICE": CostBasis.ESTIMATE,
        "UNKNOWN": CostBasis.ESTIMATE,
        "PROVIDER_FACT": CostBasis.FACT,
    }[price.evidence.basis.value]
    lines = [CostLine("purchase", price.unit_price.times(purchase_quantity), purchase_basis, price.evidence)]
    for item in (delivery, handling, unloading):
        if item is not None:
            lines.append(item)
    unknowns: list[str] = []
    if price.tax_basis is TaxBasis.VAT_INCLUDED:
        pass
    elif known_tax is not None:
        lines.append(known_tax)
    else:
        unknowns.append("tax")
    if cross_border:
        if known_duty is not None:
            lines.append(known_duty)
        else:
            unknowns.append("customs_duty")
    elif known_duty is not None:
        lines.append(known_duty)
    lines.extend(other_costs)
    warnings = []
    if price.availability.value == "UNAVAILABLE":
        warnings.append("SUPPLIER_OPTION_UNAVAILABLE")
    elif price.availability.value == "UNKNOWN":
        warnings.append("AVAILABILITY_UNKNOWN")
    return LandedCostAssessment(
        requirement.material_id,
        purchase_quantity,
        price.unit,
        assess_cost_lines(lines, unknown_components=unknowns, warnings=warnings),
        waste,
    )
