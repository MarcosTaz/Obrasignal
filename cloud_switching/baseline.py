from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, Sequence

Money = Decimal


class Certainty(str, Enum):
    KNOWN = "known"
    ESTIMATED = "estimated"
    ASSUMED = "assumed"
    UNKNOWN = "unknown"


class MissingMaterialInput(ValueError):
    pass


@dataclass(frozen=True)
class BaselineCost:
    name: str
    annual_value: Optional[Money]
    certainty: Certainty
    material: bool = True
    source_id: Optional[str] = None

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("baseline cost name is required")
        if self.certainty is Certainty.UNKNOWN:
            if self.annual_value is not None:
                raise ValueError("unknown baseline cost cannot carry a numeric value")
            return
        if self.annual_value is None:
            raise ValueError("non-unknown baseline cost requires a numeric value")
        if self.annual_value < 0:
            raise ValueError("baseline costs cannot be negative")
        if self.certainty is Certainty.KNOWN and not self.source_id:
            raise ValueError("known baseline cost requires source evidence")


@dataclass(frozen=True)
class CurrentStateBaseline:
    company_id: str
    components: Sequence[BaselineCost]

    def validate(self) -> None:
        if not self.company_id.strip():
            raise ValueError("company_id is required")
        if not self.components:
            raise ValueError("at least one baseline component is required")
        seen = set()
        for component in self.components:
            component.validate()
            if component.name in seen:
                raise ValueError(f"duplicate baseline component: {component.name}")
            seen.add(component.name)

    def unresolved_material_inputs(self) -> tuple[str, ...]:
        self.validate()
        return tuple(
            component.name
            for component in self.components
            if component.material and component.certainty is Certainty.UNKNOWN
        )

    def annual_cost(self) -> Money:
        unresolved = self.unresolved_material_inputs()
        if unresolved:
            raise MissingMaterialInput(
                "material baseline inputs unresolved: " + ", ".join(sorted(unresolved))
            )
        return sum(
            (component.annual_value or Decimal("0") for component in self.components),
            Decimal("0"),
        )

    def certainty_counts(self) -> dict[Certainty, int]:
        self.validate()
        return {
            certainty: sum(1 for component in self.components if component.certainty is certainty)
            for certainty in Certainty
        }
