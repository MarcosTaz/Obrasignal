from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re

from .money import as_decimal

_UNIT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./²³-]{0,31}$")

class UnitError(ValueError):
    pass

class IncompatibleUnitError(UnitError):
    pass

@dataclass(frozen=True, slots=True)
class UnitSpec:
    canonical: str
    dimension: str
    to_base: Decimal

_UNIT_SPECS = {
    "unit": UnitSpec("unit", "count", Decimal("1")),
    "ea": UnitSpec("unit", "count", Decimal("1")),
    "kg": UnitSpec("kg", "mass", Decimal("1")),
    "t": UnitSpec("t", "mass", Decimal("1000")),
    "tonne": UnitSpec("t", "mass", Decimal("1000")),
    "m": UnitSpec("m", "length", Decimal("1")),
    "km": UnitSpec("km", "length", Decimal("1000")),
    "m2": UnitSpec("m2", "area", Decimal("1")),
    "m²": UnitSpec("m2", "area", Decimal("1")),
    "m3": UnitSpec("m3", "volume", Decimal("1")),
    "m³": UnitSpec("m3", "volume", Decimal("1")),
    "l": UnitSpec("l", "volume_liquid", Decimal("1")),
    "litre": UnitSpec("l", "volume_liquid", Decimal("1")),
    "liter": UnitSpec("l", "volume_liquid", Decimal("1")),
    "day": UnitSpec("day", "time", Decimal("1")),
    "week": UnitSpec("week", "time", Decimal("7")),
    "night": UnitSpec("night", "night", Decimal("1")),
    "room_night": UnitSpec("room_night", "room_night", Decimal("1")),
    "person_night": UnitSpec("person_night", "person_night", Decimal("1")),
}


def normalize_unit(unit: str) -> str:
    value = str(unit or "").strip().lower()
    if not value or not _UNIT_RE.fullmatch(value):
        raise UnitError("invalid or missing unit")
    return _UNIT_SPECS.get(value, UnitSpec(value, f"opaque:{value}", Decimal("1"))).canonical


def unit_dimension(unit: str) -> str:
    raw = str(unit or "").strip().lower()
    if not raw or not _UNIT_RE.fullmatch(raw):
        raise UnitError("invalid or missing unit")
    return _UNIT_SPECS.get(raw, UnitSpec(raw, f"opaque:{raw}", Decimal("1"))).dimension


def convert_quantity(quantity: Decimal | int | str | float, from_unit: str, to_unit: str) -> Decimal:
    q = as_decimal(quantity)
    if q < 0:
        raise UnitError("quantity must be non-negative")
    f_raw, t_raw = str(from_unit).strip().lower(), str(to_unit).strip().lower()
    if f_raw not in _UNIT_SPECS or t_raw not in _UNIT_SPECS:
        if normalize_unit(from_unit) == normalize_unit(to_unit):
            return q
        raise IncompatibleUnitError(f"no safe conversion known for {from_unit} -> {to_unit}")
    f, t = _UNIT_SPECS[f_raw], _UNIT_SPECS[t_raw]
    if f.dimension != t.dimension:
        raise IncompatibleUnitError(f"cannot convert {from_unit} ({f.dimension}) to {to_unit} ({t.dimension})")
    return q * f.to_base / t.to_base
