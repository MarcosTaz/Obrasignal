"""Five-tier Global Market Portfolio vNext for ObraSignal.

This module refines the already-completed 2026-08-24 scope rebase.  It does not
restart worldwide research and it does not authorize new source/runtime work.
The existing ``market_scope_registry`` remains the evidence-preserving base;
this layer adds the TECH_LAB distinction and a richer decision record while
keeping commercial active coverage and dedicated connector count unchanged.

Governing rule: maximize commercial value per engineering hour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from market_scope_registry import (
    BUILD_ORDER,
    DECISION_UNIVERSE,
    DEDICATED_CONNECTORS,
    MARKET_SCOPE as LEGACY_SCOPE,
    OFFICIAL_ACTIVE_MARKETS,
    SHARED_FAMILIES,
    TARGET_DEDICATED_CONNECTORS,
)

PortfolioCategory = Literal["BUILD", "SHARED", "TECH_LAB", "HOLD", "REMOVE"]
Score = int | Literal["UNKNOWN"]


@dataclass(frozen=True)
class PortfolioMarket:
    country: str
    category: PortfolioCategory
    commercial_score: Score
    technical_score: Score
    reuse_score: Score
    maintenance_score: Score
    strategic_role: str
    coverage_method: str
    connector_family: str
    dedicated_connector_required: bool
    primary_blocker: str
    reconsideration_trigger: str
    decision_reason: str


# TECH LAB is deliberately small. These markets are retained for reusable
# technical learning only; they are not product launch promises and receive no
# dedicated connector roadmap merely because their public-procurement systems
# are technically interesting.
TECH_LAB_OVERRIDES = {
    "Uganda": {
        "coverage_method": "official e-GP public lifecycle / research-only",
        "connector_family": "e-GP / potential reusable lifecycle adapter",
        "primary_blocker": "Commercial reuse/API contract and paid regional demand are not yet proven strongly enough for product coverage.",
        "reconsideration_trigger": "Promote only after lawful machine access/reuse is validated and paid regional traction or a clearly reusable shared adapter justifies marginal support.",
        "decision_reason": "Official e-GP exposes procurement plans, invitations, evaluated-bid notices and contract-award lifecycle, creating high technical learning value without winning the next 100 engineering-hour commercial test.",
    },
    "Zambia": {
        "coverage_method": "official e-GP / OCDS-oriented research-only",
        "connector_family": "e-GP / potential OCDS family",
        "primary_blocker": "Stable production-grade machine endpoint, reuse terms and paid-market evidence remain insufficient for active commercial support.",
        "reconsideration_trigger": "Promote if the published machine/OCDS route proves stable and commercially reusable, preferably through the common OCDS family, with credible paid demand.",
        "decision_reason": "Active e-GP has useful procurement-plan, tender and lifecycle structure and explicit OCDS direction; this is technically reusable evidence, not a case for dedicated country engineering now.",
    },
    "Tanzania": {
        "coverage_method": "OCDS technical reference / research-only",
        "connector_family": "OCDS_API_BULK candidate",
        "primary_blocker": "Commercial ARPU/willingness-to-pay does not currently beat higher-priority markets despite strong OCDS characteristics.",
        "reconsideration_trigger": "Promote if regional paid demand appears or marginal inclusion in the shared OCDS family becomes effectively zero-cost and legally sound.",
        "decision_reason": "The prior registry already records strong OCDS technical quality but failure of the next-100-hours commercial test; TECH_LAB expresses that distinction more accurately than HOLD.",
    },
}

HOLD_OVERRIDES = {
    "Namibia": {
        "coverage_method": "official eProcurement / deferred",
        "connector_family": "national eProcurement; shared adapter only if later proven",
        "primary_blocker": "Commercial scale is limited and the current public architecture is less integration-friendly than higher-value markets; API/reuse and marginal maintenance remain unproven.",
        "reconsideration_trigger": "Reopen when a stable reusable machine route or near-zero-cost shared adapter exists, or when customer demand justifies the fragmentation/maintenance cost.",
        "decision_reason": "Namibia has official digital procurement covering plans, notices, amendments, openings, evaluations, awards and cancellations; the blocker is opportunity cost and integration burden, not absence of digital procurement.",
    }
}

REMOVE_REASON_OVERRIDES = {
    "Cabo Verde": "Cabo Verde has active e-Compras/electronic procurement. It remains outside the current phase because its small commercial scale and likely ARPU do not beat the opportunity cost of engineering/localization versus stronger markets; this is an economic-priority decision, not a data-absence claim.",
}


def _shared_family(country: str) -> str:
    for family, countries in SHARED_FAMILIES.items():
        if country in countries:
            return family
    return ""


def _role(category: PortfolioCategory) -> str:
    return {
        "BUILD": "BEACHHEAD / SCALE / PREMIUM ACTIVE MARKET",
        "SHARED": "LOW-MARGINAL-COST BREADTH",
        "TECH_LAB": "REUSABLE TECHNICAL LEARNING",
        "HOLD": "FUTURE OPTION",
        "REMOVE": "OUT OF CURRENT PHASE",
    }[category]


def _base_record(country: str) -> PortfolioMarket:
    base = LEGACY_SCOPE[country]
    category: PortfolioCategory = base.status
    reason = REMOVE_REASON_OVERRIDES.get(country, base.reason)
    family = _shared_family(country)
    coverage = base.infrastructure or (family if family else "none / deferred")
    dedicated = country in DEDICATED_CONNECTORS
    blocker = ""
    trigger = base.reopen_condition
    if category == "BUILD":
        blocker = "No portfolio blocker; source-specific production gates still apply."
    elif category == "SHARED":
        blocker = "No dedicated-country engineering justified while the shared family delivers the required scope."
        trigger = "Reconsider bespoke enrichment only after paid demand proves a material product gap that the shared family cannot close."
    elif category == "REMOVE":
        blocker = reason
        trigger = "Reconsider only on objective new customer, partnership, data/API, legal/reuse or strategic evidence."
    return PortfolioMarket(
        country=country,
        category=category,
        commercial_score="UNKNOWN",
        technical_score="UNKNOWN",
        reuse_score="UNKNOWN",
        maintenance_score="UNKNOWN",
        strategic_role=_role(category),
        coverage_method=coverage,
        connector_family=family or base.infrastructure,
        dedicated_connector_required=dedicated,
        primary_blocker=blocker,
        reconsideration_trigger=trigger,
        decision_reason=reason,
    )


def _override(base: PortfolioMarket, category: PortfolioCategory, values: dict[str, str]) -> PortfolioMarket:
    return PortfolioMarket(
        country=base.country,
        category=category,
        commercial_score=base.commercial_score,
        technical_score=base.technical_score,
        reuse_score=base.reuse_score,
        maintenance_score=base.maintenance_score,
        strategic_role=_role(category),
        coverage_method=values.get("coverage_method", base.coverage_method),
        connector_family=values.get("connector_family", base.connector_family),
        dedicated_connector_required=False if category != "BUILD" else base.dedicated_connector_required,
        primary_blocker=values.get("primary_blocker", base.primary_blocker),
        reconsideration_trigger=values.get("reconsideration_trigger", base.reconsideration_trigger),
        decision_reason=values.get("decision_reason", base.decision_reason),
    )


GLOBAL_MARKET_PORTFOLIO = {country: _base_record(country) for country in LEGACY_SCOPE}
for _country, _values in TECH_LAB_OVERRIDES.items():
    GLOBAL_MARKET_PORTFOLIO[_country] = _override(GLOBAL_MARKET_PORTFOLIO[_country], "TECH_LAB", _values)
for _country, _values in HOLD_OVERRIDES.items():
    GLOBAL_MARKET_PORTFOLIO[_country] = _override(GLOBAL_MARKET_PORTFOLIO[_country], "HOLD", _values)


def portfolio_market(country: str) -> PortfolioMarket:
    try:
        return GLOBAL_MARKET_PORTFOLIO[country]
    except KeyError as exc:
        raise KeyError(f"market is not in Global Market Portfolio vNext: {country}") from exc


def portfolio_counts() -> dict[str, int]:
    return {
        category: sum(1 for market in GLOBAL_MARKET_PORTFOLIO.values() if market.category == category)
        for category in ("BUILD", "SHARED", "TECH_LAB", "HOLD", "REMOVE")
    }


def commercially_active_markets() -> tuple[str, ...]:
    return tuple(sorted(country for country, market in GLOBAL_MARKET_PORTFOLIO.items() if market.category in {"BUILD", "SHARED"}))


def dedicated_engineering_allowed(country: str) -> bool:
    return portfolio_market(country).category == "BUILD"


def tech_lab_markets() -> tuple[str, ...]:
    return tuple(sorted(country for country, market in GLOBAL_MARKET_PORTFOLIO.items() if market.category == "TECH_LAB"))


def validate_portfolio() -> None:
    counts = portfolio_counts()
    if len(GLOBAL_MARKET_PORTFOLIO) != DECISION_UNIVERSE:
        raise RuntimeError("portfolio no longer covers the complete reviewed universe")
    if counts != {"BUILD": 14, "SHARED": 31, "TECH_LAB": 3, "HOLD": 26, "REMOVE": 61}:
        raise RuntimeError(f"unexpected portfolio counts: {counts}")
    if len(commercially_active_markets()) != OFFICIAL_ACTIVE_MARKETS:
        raise RuntimeError("commercial active coverage changed unexpectedly")
    if len(DEDICATED_CONNECTORS) != TARGET_DEDICATED_CONNECTORS:
        raise RuntimeError("dedicated connector target changed unexpectedly")
    if any(portfolio_market(country).category != "BUILD" for country in DEDICATED_CONNECTORS):
        raise RuntimeError("dedicated connector exists outside BUILD")
    if set(BUILD_ORDER) != {country for country, market in GLOBAL_MARKET_PORTFOLIO.items() if market.category == "BUILD"}:
        raise RuntimeError("BUILD order and portfolio BUILD set diverged")


validate_portfolio()
