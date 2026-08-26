"""Narrow official-evidence observations for HOLD reopen monitors.

This module does not change strategic scope. It records only decision-changing
facts for existing HOLD triggers so the Factory can avoid repeating full country
research when the exact reopen condition remains false.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from global_market_expansion_factory import HOLD_MONITORS

TriggerState = Literal["TRIGGER_FALSE", "TRIGGER_PARTIAL", "TRIGGER_TRUE", "UNKNOWN"]


@dataclass(frozen=True)
class HoldEvidenceObservation:
    country: str
    observed_at: str
    official_authority: str
    evidence_urls: tuple[str, ...]
    trigger_state: TriggerState
    proven_now: tuple[str, ...]
    missing_now: tuple[str, ...]
    interpretation: str


SOUTH_KOREA = HoldEvidenceObservation(
    country="South Korea",
    observed_at="2026-08-26",
    official_authority="Public Procurement Service / data.go.kr",
    evidence_urls=(
        "https://www.data.go.kr/data/15129394/openapi.do",
        "https://www.data.go.kr/catalog/15129394/openapi.json",
    ),
    trigger_state="TRIGGER_FALSE",
    proven_now=(
        "official REST OpenAPI",
        "JSON+XML",
        "nationwide coverage",
        "construction-specific bid-notice operation",
        "real-time update cadence",
        "free",
        "development and production approval automatic",
        "published licence scope states no restrictions",
    ),
    missing_now=(
        "project KONEPS_SERVICE_KEY",
        "bounded live project-key proof of paging/change identity/lifecycle",
    ),
    interpretation=(
        "Do not repeat broad KONEPS source/legal discovery. Current official evidence "
        "narrows the reopen gate to project credential availability plus bounded live contract validation."
    ),
)


AUSTRALIA = HoldEvidenceObservation(
    country="Australia",
    observed_at="2026-08-26",
    official_authority="Australian Government Department of Finance / AusTender",
    evidence_urls=(
        "https://sellingtogov.finance.gov.au/faq/using-austender",
        "https://www.finance.gov.au/publications/resource-management-guides/procurement-publishing-and-reporting-obligations-rmg-423/approaching-market",
    ),
    trigger_state="TRIGGER_FALSE",
    proven_now=(
        "AusTender is the central federal procurement publication system",
        "all open approaches to market are published on AusTender",
        "annual procurement plans and awarded contracts are published",
        "current ATM documents are human-accessible/downloadable",
    ),
    missing_now=(
        "official production-safe machine-readable live ATM route",
        "source-scoped commercial reuse/redistribution terms for that route",
    ),
    interpretation=(
        "Human/public coverage is strong but does not satisfy the Factory machine-access + reuse trigger. "
        "Keep HOLD and monitor only those two missing facts rather than re-running full market research."
    ),
)


INDIA = HoldEvidenceObservation(
    country="India",
    observed_at="2026-08-26",
    official_authority="Central Public Procurement Portal / National Informatics Centre",
    evidence_urls=(
        "https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders",
        "https://eprocure.gov.in/eprocure/app?page=FrontEndAdvancedSearch&service=page",
    ),
    trigger_state="TRIGGER_FALSE",
    proven_now=(
        "current active central-government tender publication",
        "construction tenders are present in current results",
        "latest tender/corrigendum surfaces update frequently",
        "tender schedules are publicly downloadable at no cost",
    ),
    missing_now=(
        "official broad machine-readable tender API/feed or bulk route",
        "production-safe discovery not dependent on CAPTCHA/manual search",
        "source-scoped commercial reuse/redistribution terms for the selected machine route",
    ),
    interpretation=(
        "The market/source is active, but current official discovery remains human/interactive for the tested route. "
        "Do not bypass CAPTCHA and do not reopen connector engineering until a sanctioned broad machine route is proven."
    ),
)


MEXICO = HoldEvidenceObservation(
    country="Mexico",
    observed_at="2026-08-26",
    official_authority="Secretaría Anticorrupción y Buen Gobierno / ComprasMX",
    evidence_urls=(
        "https://comprasmx.buengobierno.gob.mx/compras-mx",
        "https://comprasmx.buengobierno.gob.mx/datos-abiertos",
    ),
    trigger_state="TRIGGER_FALSE",
    proven_now=(
        "official ComprasMX public procurement portal",
        "public historical procurement consultation",
        "official open-data downloads are advertised for procurement records/contracts",
    ),
    missing_now=(
        "stable official live/incremental opportunity route",
        "current API/feed pagination and update contract",
        "source-scoped commercial reuse/redistribution terms for the selected live route",
    ),
    interpretation=(
        "Public downloads improve discovery evidence but do not satisfy the live/incremental source contract required by the reopen trigger. "
        "Monitor the official machine route/API contract instead of repeatedly researching the whole Mexican market."
    ),
)


HOLD_EVIDENCE_OBSERVATIONS = MappingProxyType({
    SOUTH_KOREA.country: SOUTH_KOREA,
    AUSTRALIA.country: AUSTRALIA,
    INDIA.country: INDIA,
    MEXICO.country: MEXICO,
})


def reopen_trigger_satisfied(country: str) -> bool:
    observation = HOLD_EVIDENCE_OBSERVATIONS.get(country)
    return observation is not None and observation.trigger_state == "TRIGGER_TRUE"


def validate_hold_evidence() -> None:
    if not set(HOLD_EVIDENCE_OBSERVATIONS) <= set(HOLD_MONITORS):
        raise RuntimeError("HOLD evidence may only attach to current strategic HOLD markets")
    if SOUTH_KOREA.trigger_state != "TRIGGER_FALSE":
        raise RuntimeError("KONEPS cannot reopen without project credential + live contract proof")
    if "project KONEPS_SERVICE_KEY" not in SOUTH_KOREA.missing_now:
        raise RuntimeError("South Korea credential gate was lost")
    if AUSTRALIA.trigger_state != "TRIGGER_FALSE":
        raise RuntimeError("Australia cannot reopen without machine route + reuse proof")
    if INDIA.trigger_state != "TRIGGER_FALSE" or "CAPTCHA" not in " ".join(INDIA.missing_now):
        raise RuntimeError("India must remain fail-closed without a sanctioned broad machine route")
    if MEXICO.trigger_state != "TRIGGER_FALSE" or "live/incremental" not in " ".join(MEXICO.missing_now):
        raise RuntimeError("Mexico must remain fail-closed without a stable live/incremental route")
    if any(reopen_trigger_satisfied(country) for country in HOLD_EVIDENCE_OBSERVATIONS):
        raise RuntimeError("no observed HOLD trigger is currently satisfied")


validate_hold_evidence()
