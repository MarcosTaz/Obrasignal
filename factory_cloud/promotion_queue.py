from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factory_cloud.control_plane import load_registry
from factory_cloud.factory_switchboard import load_switchboard
from factory_cloud.portfolio import load_portfolio, portfolio_index


@dataclass(frozen=True)
class PromotionCandidate:
    factory_id: str
    family: str
    maturity: str
    source_status: str
    app_registered: bool
    state: str
    blocker: str


_MATURITY_RANK = {"G6": 6, "G5": 5, "G4": 4, "G3": 3, "G2": 2, "G1": 1, "G0": 0, "UNASSESSED": -1}


def build_promotion_queue(
    *,
    switchboard: dict[str, Any] | None = None,
    portfolio: dict[str, Any] | None = None,
    app_registry: dict[str, Any] | None = None,
) -> tuple[PromotionCandidate, ...]:
    switchboard = switchboard or load_switchboard()
    portfolio = portfolio or load_portfolio()
    app_registry = app_registry or load_registry()

    switch_ids = {str(item["id"]) for item in switchboard.get("factories", [])}
    portfolio_by_id = portfolio_index(portfolio)
    app_ids = {str(item["app_id"]) for item in app_registry.get("applications", [])}

    candidates: list[PromotionCandidate] = []
    for factory_id in sorted(switch_ids):
        item = portfolio_by_id[factory_id]
        if item.get("layer") != "verticals":
            continue
        source_status = str(item.get("source_status") or "")
        maturity = str(item.get("maturity") or "UNASSESSED")
        family = str(item.get("family") or "")
        registered = factory_id in app_ids
        if registered:
            state = "APP_REGISTERED"
            blocker = ""
        else:
            state = "PROMOTION_BLOCKED"
            blocker = "canonical_application_source_truth_required"
        candidates.append(PromotionCandidate(
            factory_id=factory_id,
            family=family,
            maturity=maturity,
            source_status=source_status,
            app_registered=registered,
            state=state,
            blocker=blocker,
        ))

    return tuple(sorted(
        candidates,
        key=lambda item: (
            item.app_registered,
            -_MATURITY_RANK.get(item.maturity, -2),
            item.factory_id,
        ),
    ))
