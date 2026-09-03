"""Fail-closed country launch registry for ObraSignal.

This module is a commercial launch-readiness layer only. It consumes the
canonical Global Market Portfolio and source production gates; it never
redefines legal/source truth and never authorizes production launch, paid spend,
or commercial commitments.

A BUILD/SHARED market is not automatically launch-ready. Unknown source binding,
failed source gates, incomplete country localization, pricing, ICP or channel
evidence remain explicit blockers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from global_market_portfolio import GLOBAL_MARKET_PORTFOLIO
from market_scope_registry import SHARED_FAMILIES
from source_registry import SOURCES, production_gate_reasons

LaunchState = Literal[
    "NOT_ELIGIBLE",
    "UPSTREAM_PENDING",
    "LAUNCH_RESEARCH",
    "LOCALIZATION_PENDING",
    "ICP_PENDING",
    "PRICING_PENDING",
    "CHANNEL_PENDING",
    "LAUNCH_CANDIDATE",
    "SOFT_LAUNCH_READY",
    "SOFT_LAUNCH_ACTIVE",
    "FIRST_USERS",
    "FIRST_VALUE_PROVEN",
    "FIRST_REVENUE",
    "RETENTION_UNKNOWN",
    "RETENTION_PROVEN",
    "SCALE_CANDIDATE",
    "SCALE_ACTIVE",
    "HOLD",
    "EXIT",
]

LocalizationClass = Literal[
    "TRANSLATION_ONLY",
    "SEMANTIC_LOCALIZATION",
    "WORKFLOW_LOCALIZATION",
    "REGULATORY_LOCALIZATION",
    "UNKNOWN",
]
PriorityDecision = Literal["LAUNCH_NOW", "PREPARE", "MONITOR", "HOLD"]
EvidenceState = Literal["PROVEN", "PARTIAL", "HYPOTHESIS", "UNKNOWN", "BLOCKED"]


@dataclass(frozen=True)
class CountryLaunch:
    country: str
    upstream_state: str
    launch_state: LaunchState
    source_bindings: tuple[str, ...]
    product_coverage: str
    language: str
    currency: str
    timezone: str
    localization_class: LocalizationClass
    workflow_state: EvidenceState
    icp_state: EvidenceState
    pricing_state: EvidenceState
    channel_state: EvidenceState
    trust_state: EvidenceState
    priority: PriorityDecision
    blocker: str
    last_reviewed: str


BUILD_SOURCE_BINDINGS = {
    "Portugal": ("BASE", "TED"),
    "Spain": ("PLACSP", "TED"),
    "Italy": ("IT_ANAC", "TED"),
    "France": ("BOAMP", "TED"),
    "Germany": ("SERVICE_BUND_DE", "TED"),
    "Switzerland": ("CH_SIMAP",),
    "United Kingdom": ("UK_PROCUREMENT",),
    "Netherlands": ("NL_TENDERNED", "TED"),
    "Poland": ("PL_BZP", "TED"),
    # BR_PNCP is intentionally not invented in source_registry.py. The current
    # canonical queue records the production connector as gated on live
    # transport reliability, so launch work must fail closed here.
    "Brazil": (),
    "Canada": ("CA_CANADABUYS",),
    "United States": ("US_SAM",),
    "Colombia": ("CO_SECOP",),
    "Chile": ("CL_MERCADOPUBLICO",),
}

# Only shared-country bindings explicitly evidenced by the current source
# registry are admitted here. Missing bindings are an upstream evidence gap,
# not an instruction to remove the market from SHARED portfolio scope.
SHARED_OCDS_SOURCE_BINDINGS = {
    "Ecuador": ("EC_SERCOP",),
    "Paraguay": ("PY_DNCP",),
    "South Africa": ("ZA_ETENDERS",),
    "Uruguay": ("UY_ARCE",),
}

BUILD_LOCAL_CONTEXT = {
    "Portugal": ("Portuguese", "EUR", "Europe/Lisbon", "SEMANTIC_LOCALIZATION"),
    "Spain": ("Spanish", "EUR", "Europe/Madrid", "WORKFLOW_LOCALIZATION"),
    "Italy": ("Italian", "EUR", "Europe/Rome", "REGULATORY_LOCALIZATION"),
    "France": ("French", "EUR", "Europe/Paris", "WORKFLOW_LOCALIZATION"),
    "Germany": ("German", "EUR", "Europe/Berlin", "WORKFLOW_LOCALIZATION"),
    "Switzerland": ("German/French/Italian", "CHF", "Europe/Zurich", "WORKFLOW_LOCALIZATION"),
    "United Kingdom": ("English", "GBP", "Europe/London", "REGULATORY_LOCALIZATION"),
    "Netherlands": ("Dutch", "EUR", "Europe/Amsterdam", "WORKFLOW_LOCALIZATION"),
    "Poland": ("Polish", "PLN", "Europe/Warsaw", "WORKFLOW_LOCALIZATION"),
    "Brazil": ("Portuguese (Brazil)", "BRL", "multiple", "REGULATORY_LOCALIZATION"),
    "Canada": ("English/French", "CAD", "multiple", "WORKFLOW_LOCALIZATION"),
    "United States": ("English", "USD", "multiple", "REGULATORY_LOCALIZATION"),
    "Colombia": ("Spanish", "COP", "America/Bogota", "REGULATORY_LOCALIZATION"),
    "Chile": ("Spanish", "CLP", "America/Santiago", "REGULATORY_LOCALIZATION"),
}

FIRST_WAVE = {
    "Portugal",
    "Spain",
    "United Kingdom",
    "France",
    "Italy",
}


def _source_bindings(country: str, upstream_state: str) -> tuple[str, ...]:
    if upstream_state == "BUILD":
        return BUILD_SOURCE_BINDINGS.get(country, ())
    if upstream_state != "SHARED":
        return ()
    if country in SHARED_FAMILIES.get("TED_EFORMS", ()):
        return ("TED",)
    return SHARED_OCDS_SOURCE_BINDINGS.get(country, ())


def _coverage(country: str, upstream_state: str, bindings: tuple[str, ...]) -> str:
    if country == "United States":
        return "SAM.gov federal construction only; SLED coverage is not implied"
    if country == "Canada":
        return "CanadaBuys federal construction only; provincial/municipal coverage is not implied"
    if country == "France":
        return "BOAMP + TED explicitly bound; DECP completeness requires separate proof before any coverage claim"
    if country == "Brazil":
        return "PNCP/PCA research exists upstream; production source gate is not currently launch-safe"
    if country == "Chile":
        return "Mercado Publico connector exists but requires production credential before launch use"
    if upstream_state == "SHARED" and country in SHARED_FAMILIES.get("TED_EFORMS", ()):
        return "TED/eForms shared coverage only; national/below-threshold coverage is not implied"
    if upstream_state == "SHARED":
        return "shared OCDS/API coverage only where an explicit current source binding exists"
    return " + ".join(bindings) if bindings else "UNKNOWN"


def _source_blocker(country: str, upstream_state: str, bindings: tuple[str, ...]) -> str:
    if upstream_state not in {"BUILD", "SHARED"}:
        return "upstream market is not BUILD/SHARED"
    if country == "Brazil":
        return "upstream production source is gated; stable live PNCP production-path validation is still required"
    if not bindings:
        return "no explicit launch-safe source binding exists in the current source registry"
    failures = []
    for source in bindings:
        if source not in SOURCES:
            failures.append(f"{source}:source_not_registered")
            continue
        failures.extend(f"{source}:{reason}" for reason in production_gate_reasons(source))
    if failures:
        return "; ".join(sorted(set(failures)))
    return ""


def _launch_state(upstream_state: str, blocker: str) -> LaunchState:
    if upstream_state == "REMOVE":
        return "NOT_ELIGIBLE"
    if upstream_state in {"HOLD", "TECH_LAB"}:
        return "HOLD"
    if blocker:
        return "UPSTREAM_PENDING"
    return "LAUNCH_RESEARCH"


def _priority(country: str, upstream_state: str, blocker: str) -> PriorityDecision:
    if upstream_state not in {"BUILD", "SHARED"} or blocker:
        return "HOLD" if upstream_state == "BUILD" else "MONITOR"
    if country in FIRST_WAVE:
        return "LAUNCH_NOW"
    if upstream_state == "BUILD":
        return "PREPARE"
    return "MONITOR"


def _evidence_states(country: str, launch_state: LaunchState):
    if launch_state != "LAUNCH_RESEARCH":
        return ("BLOCKED",) * 5
    # First-wave workflow/ICP/pricing/channel work has public evidence, but no
    # country launch has yet earned PROVEN status from qualified ObraSignal user
    # cohorts. Preserve that distinction explicitly.
    if country in FIRST_WAVE:
        return ("PARTIAL", "HYPOTHESIS", "HYPOTHESIS", "HYPOTHESIS", "PARTIAL")
    return ("UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN")


def _record(country: str) -> CountryLaunch:
    market = GLOBAL_MARKET_PORTFOLIO[country]
    upstream_state = market.category
    bindings = _source_bindings(country, upstream_state)
    blocker = _source_blocker(country, upstream_state, bindings)
    launch_state = _launch_state(upstream_state, blocker)
    workflow, icp, pricing, channel, trust = _evidence_states(country, launch_state)
    language, currency, timezone, localization = BUILD_LOCAL_CONTEXT.get(
        country, ("UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN")
    )
    return CountryLaunch(
        country=country,
        upstream_state=upstream_state,
        launch_state=launch_state,
        source_bindings=bindings,
        product_coverage=_coverage(country, upstream_state, bindings),
        language=language,
        currency=currency,
        timezone=timezone,
        localization_class=localization,
        workflow_state=workflow,
        icp_state=icp,
        pricing_state=pricing,
        channel_state=channel,
        trust_state=trust,
        priority=_priority(country, upstream_state, blocker),
        blocker=blocker,
        last_reviewed="2026-08-26",
    )


COUNTRY_LAUNCH_REGISTRY = {country: _record(country) for country in GLOBAL_MARKET_PORTFOLIO}


def launch_market(country: str) -> CountryLaunch:
    try:
        return COUNTRY_LAUNCH_REGISTRY[country]
    except KeyError as exc:
        raise KeyError(f"market is not in country launch registry: {country}") from exc


def launch_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in COUNTRY_LAUNCH_REGISTRY.values():
        counts[record.launch_state] = counts.get(record.launch_state, 0) + 1
    return dict(sorted(counts.items()))


def first_wave() -> tuple[str, ...]:
    return tuple(
        country for country in ("Portugal", "Spain", "United Kingdom", "France", "Italy")
        if launch_market(country).priority == "LAUNCH_NOW"
    )


def upstream_pending_markets() -> tuple[str, ...]:
    return tuple(sorted(
        country for country, record in COUNTRY_LAUNCH_REGISTRY.items()
        if record.launch_state == "UPSTREAM_PENDING"
    ))


def validate_country_launch_registry() -> None:
    if set(COUNTRY_LAUNCH_REGISTRY) != set(GLOBAL_MARKET_PORTFOLIO):
        raise RuntimeError("country launch registry no longer covers the upstream portfolio universe")
    if any(record.upstream_state not in {"BUILD", "SHARED"} and record.launch_state == "LAUNCH_RESEARCH"
           for record in COUNTRY_LAUNCH_REGISTRY.values()):
        raise RuntimeError("non-active upstream market entered launch research")
    if any(record.launch_state == "LAUNCH_RESEARCH" and record.blocker
           for record in COUNTRY_LAUNCH_REGISTRY.values()):
        raise RuntimeError("blocked country entered launch research")
    if launch_market("United States").product_coverage.find("SLED coverage is not implied") < 0:
        raise RuntimeError("US federal-only boundary was lost")
    if launch_market("Canada").product_coverage.find("provincial/municipal coverage is not implied") < 0:
        raise RuntimeError("Canada federal-only boundary was lost")
    for country in SHARED_FAMILIES.get("TED_EFORMS", ()):
        record = launch_market(country)
        if "national/below-threshold coverage is not implied" not in record.product_coverage:
            raise RuntimeError(f"TED completeness boundary was lost for {country}")
    for country in FIRST_WAVE:
        if launch_market(country).launch_state != "LAUNCH_RESEARCH":
            raise RuntimeError(f"first-wave country is no longer launch-research safe: {country}")


validate_country_launch_registry()
