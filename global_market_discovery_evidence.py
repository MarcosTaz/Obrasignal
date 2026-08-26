"""Structured evidence for jurisdictions outside the canonical 135.

Discovery evidence can narrow the next check, but cannot promote a market.
Public access is not commercial reuse; an interactive portal is not a machine
contract; a historical open dataset is not a current feed.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

DiscoveryState = Literal["DISCOVERED", "RESEARCHING"]
LegalState = Literal["LEGAL_GREEN", "LEGAL_AMBER", "LEGAL_RED", "LEGAL_UNKNOWN"]
TechnicalState = Literal["TECHNICAL_GREEN", "TECHNICAL_PARTIAL", "TECHNICAL_BLOCKED", "TECHNICAL_UNKNOWN"]


@dataclass(frozen=True)
class DiscoveryEvidence:
    country: str
    state: DiscoveryState
    authority: str
    official_portal: str
    legal_state: LegalState
    technical_state: TechnicalState
    source_observation: str
    commercial_observation: str
    evidence_urls: tuple[str, ...]
    last_checked: str
    next_check: str
    reopen_query: str
    exact_gap: str


TURKEY = DiscoveryEvidence(
    country="Turkey",
    state="RESEARCHING",
    authority="Kamu İhale Kurumu (Public Procurement Authority)",
    official_portal="EKAP — Elektronik Kamu Alımları Platformu",
    legal_state="LEGAL_UNKNOWN",
    technical_state="TECHNICAL_BLOCKED",
    source_observation=(
        "EKAP is the official national platform and exposes tender notices, documents and contract-result information. "
        "The public tender-search route observed on 2026-08-26 requires JavaScript plus an interactive question/number challenge. "
        "The official procurement bulletin is downloadable as PDF and the publisher states the PDF bulletin prevails if portal text conflicts. "
        "No official structured public API/feed with a production-safe contract was proven in this research pass."
    ),
    commercial_observation=(
        "EKAP access/membership and notice/document access are described as free, but free/public access is not evidence of commercial reuse, redistribution or derivative rights."
    ),
    evidence_urls=(
        "https://ekap.kik.gov.tr/ekap/ortak/ksp/kspihalearama.aspx",
        "https://ekap.kik.gov.tr/EKAP/Ilan/BultenIndirme.aspx",
        "https://ekap.kik.gov.tr/ekap/DuyuruDetay.aspx",
    ),
    last_checked="2026-08-26",
    next_check="2026-09-26",
    reopen_query="Official KİK/EKAP machine-readable tender API/feed or bulk dataset + explicit commercial reuse/redistribution terms",
    exact_gap="No authorized structured machine route and no source-scoped commercial reuse licence were proven; interactive challenge must not be bypassed.",
)


SERBIA = DiscoveryEvidence(
    country="Serbia",
    state="RESEARCHING",
    authority="Public Procurement Office / Канцеларија за јавне набавке",
    official_portal="Portal javnih nabavki",
    legal_state="LEGAL_UNKNOWN",
    technical_state="TECHNICAL_UNKNOWN",
    source_observation=(
        "The current public portal exposes procurement plans, procedures, notices, award/suspension decisions, contracts and CPV classifications, with current 2026 activity. "
        "Serbian procurement law is quoted by an official ministry as granting interested persons free, unlimited and direct access to search, view and download published notices and procurement documentation. "
        "The national open-data portal has a procurement-notice dataset, but the located resources belong to the old portal and the current-month resource shown was last modified in 2020; it cannot be treated as a current 2026 feed. "
        "No current official procurement API/feed contract was proven in this pass."
    ),
    commercial_observation=(
        "Free/unlimited/direct access supports public availability but does not by itself establish commercial redistribution/derivative rights; current-source legal reuse remains unresolved."
    ),
    evidence_urls=(
        "https://jnportal.ujn.gov.rs/",
        "https://data.gov.rs/sr/datasets/podatsi-iz-oglasa-javnikh-nabavki-sa-portala-javnikh-nabavki/",
        "https://www.mre.gov.rs/tekst/sr/96/javne-nabavke-.php",
    ),
    last_checked="2026-08-26",
    next_check="2026-09-02",
    reopen_query="Current official jnportal machine API/feed/export or documented data service + source-scoped commercial reuse licence",
    exact_gap="Current national portal is rich and public, but current machine ingestion and commercial reuse rights are not yet proven; legacy 2020 open-data resources are stale for production discovery.",
)


DISCOVERY_EVIDENCE = MappingProxyType({
    "Turkey": TURKEY,
    "Serbia": SERBIA,
})


def validate_discovery_evidence() -> None:
    if set(DISCOVERY_EVIDENCE) != {"Turkey", "Serbia"}:
        raise RuntimeError("first discovery evidence cell must preserve Turkey and Serbia")
    if any(record.state not in {"DISCOVERED", "RESEARCHING"} for record in DISCOVERY_EVIDENCE.values()):
        raise RuntimeError("discovery evidence cannot promote a jurisdiction")
    if TURKEY.legal_state != "LEGAL_UNKNOWN" or SERBIA.legal_state != "LEGAL_UNKNOWN":
        raise RuntimeError("public access must not be upgraded to commercial reuse by inference")
    if "bypass" not in TURKEY.exact_gap:
        raise RuntimeError("Turkey interactive access-control constraint must remain explicit")
    if "2020" not in SERBIA.exact_gap:
        raise RuntimeError("Serbia legacy open-data staleness must remain explicit")


validate_discovery_evidence()
