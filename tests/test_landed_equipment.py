from datetime import datetime, timezone
from decimal import Decimal
import pytest

from bangs.costs import CostBasis, CostCompleteness, CostLine
from bangs.equipment import EquipmentMode, EquipmentOption, RentalRateBasis, assess_equipment
from bangs.evidence import Availability, EvidenceBasis, RequirementBasis, SourceEvidence, TaxBasis, Visibility
from bangs.landed_cost import assess_landed_cost
from bangs.materials import MaterialPriceObservation, MaterialRequirement
from bangs.money import Money, MoneyError

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
EV = SourceEvidence("catalogue", EvidenceBasis.OFFICIAL_CATALOGUE, NOW)

def req(q="2000", unit="m2"):
    return MaterialRequirement("x", "Material X", Decimal(q), unit, RequirementBasis.BOQ_EXPLICIT)

def price(amount="8", unit="m2", tax=TaxBasis.VAT_INCLUDED, minq=None, availability=Availability.AVAILABLE, currency="EUR"):
    return MaterialPriceObservation("p", "x", "A", unit, Money.of(amount, currency), tax, EV, Visibility.PUBLIC, minimum_quantity=minq, availability=availability)

def line(code, amount, currency="EUR"):
    return CostLine(code, Money.of(amount, currency), CostBasis.ESTIMATE, EV)

def test_landed_cost_is_purchase_plus_logistics_not_raw_price():
    result = assess_landed_cost(req(), price(), delivery=line("delivery", 500), handling=line("handling", 100), unloading=line("unloading", 50))
    assert result.assessment.known_total.amount == Decimal("16650")
    assert result.assessment.completeness is CostCompleteness.COMPLETE_WITHIN_DECLARED_SCOPE

def test_minimum_quantity_and_explicit_waste_are_honoured():
    result = assess_landed_cost(req("80"), price("10", minq=Decimal("100")), waste_fraction=Decimal("0.05"))
    assert result.purchase_quantity == Decimal("105.00")
    assert result.assessment.known_total.amount == Decimal("1050.00")

def test_no_universal_waste_assumption():
    result = assess_landed_cost(req("100"), price("10"))
    assert result.purchase_quantity == Decimal("100")
    assert result.waste_fraction is None

def test_tax_unknown_and_cross_border_customs_do_not_become_zero():
    partial = assess_landed_cost(req("10"), price("10", tax=TaxBasis.TAX_UNKNOWN), cross_border=True)
    assert partial.assessment.known_total.amount == 100
    assert set(partial.assessment.unknown_components) == {"tax", "customs_duty"}
    assert partial.assessment.completeness is CostCompleteness.PARTIAL_TOTAL

def test_explicit_tax_and_duty_can_complete_declared_scope():
    result = assess_landed_cost(req("10"), price("10", tax=TaxBasis.VAT_EXCLUDED), known_tax=line("tax", 23), known_duty=line("duty", 5), cross_border=True)
    assert result.assessment.known_total.amount == 128
    assert not result.assessment.unknown_components

def test_multi_currency_landed_cost_fails_closed():
    result = assess_landed_cost(req("10"), price("10"), delivery=line("delivery", 5, "PLN"))
    assert result.assessment.known_total is None
    assert result.assessment.completeness is CostCompleteness.INSUFFICIENT_FOR_TOTAL
    assert "MULTI_CURRENCY_UNRESOLVED" in result.assessment.warnings

def test_negative_cost_is_invalid():
    with pytest.raises(MoneyError): Money.of(-1, "EUR")

def equipment(mode=EquipmentMode.RENT, **kw):
    defaults = dict(
        option_id="lift", equipment_type="platform", mode=mode, quantity=1,
        rate=Money.of(600, "EUR"), rate_basis=RentalRateBasis.WEEKLY if mode is EquipmentMode.RENT else None,
        periods=Decimal("8") if mode is EquipmentMode.RENT else Decimal("1"),
        availability=Availability.AVAILABLE, evidence=EV,
    )
    defaults.update(kw)
    return EquipmentOption(**defaults)

def test_equipment_rental_cost_and_transport_are_separate():
    a = assess_equipment(equipment(transport=Money.of(300, "EUR")))
    assert a.economic.known_total.amount == Decimal("5100")
    assert {x.code for x in a.economic.lines} == {"equipment_rate", "equipment_transport"}

def test_deposit_is_cash_outlay_not_economic_cost():
    a = assess_equipment(equipment(deposit=Money.of(1000, "EUR")))
    assert a.economic.known_total.amount == Decimal("4800")
    assert a.cash_outlay.known_total.amount == Decimal("5800")
    assert any(x.code == "deposit" and x.cash_only for x in a.cash_outlay.lines)

def test_buy_is_not_rent_and_has_no_rate_basis():
    b = assess_equipment(equipment(EquipmentMode.BUY, rate=Money.of(20000, "EUR"), periods=1))
    assert b.economic.known_total.amount == 20000
    with pytest.raises(ValueError): equipment(EquipmentMode.BUY, rate_basis=RentalRateBasis.WEEKLY)

def test_equipment_availability_unknown_is_warning_not_zero():
    a = assess_equipment(equipment(availability=Availability.UNKNOWN))
    assert a.economic.known_total.amount == 4800
    assert "AVAILABILITY_UNKNOWN" in a.economic.warnings

def test_invalid_rental_duration_rejected():
    with pytest.raises(ValueError): equipment(periods=0)
