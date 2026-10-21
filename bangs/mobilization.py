from __future__ import annotations

from dataclasses import dataclass

from .costs import CostAssessment, CostLine, assess_cost_lines

@dataclass(frozen=True, slots=True)
class MobilizationAssessment:
    mobilization: CostAssessment
    demobilization: CostAssessment | None


def compose_mobilization(
    *,
    crew_travel: CostLine | None = None,
    vehicle_cost: CostLine | None = None,
    equipment_transport: CostLine | None = None,
    materials_transport: CostLine | None = None,
    temporary_setup: CostLine | None = None,
    initial_accommodation: CostLine | None = None,
    site_establishment: CostLine | None = None,
    permits_fees: CostLine | None = None,
    other: tuple[CostLine, ...] = (),
    unknown_components: tuple[str, ...] = (),
    demobilization_lines: tuple[CostLine, ...] = (),
    demobilization_unknowns: tuple[str, ...] = (),
) -> MobilizationAssessment:
    lines = tuple(x for x in (
        crew_travel, vehicle_cost, equipment_transport, materials_transport,
        temporary_setup, initial_accommodation, site_establishment, permits_fees,
    ) if x is not None) + tuple(other)
    mobilization = assess_cost_lines(lines, unknown_components=unknown_components)
    demobilization = None
    if demobilization_lines or demobilization_unknowns:
        demobilization = assess_cost_lines(demobilization_lines, unknown_components=demobilization_unknowns)
    return MobilizationAssessment(mobilization, demobilization)
