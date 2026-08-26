"""Operational registry for Global Market Expansion, Source Legality & Country Automation.

This is an additive evidence/composition layer. It does not replace:
- ``global_market_portfolio.py`` for strategic portfolio decisions;
- ``market_scope_registry.py`` for the evidence-preserving legacy scope;
- ``source_registry.py`` for runtime/source-readiness metadata;
- ``global_market_source_contracts.py`` for Priority-A technical contracts;
- Integration Lab, Golden, Release, Security, Privacy, Contracts or Temporal authority.

The governing invariant is fail-closed: strategic BUILD/SHARED, connector existence,
HTTP success, historical legal GREEN, or a green PR are never enough to produce
ACTIVE_PROVEN here.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Literal

from global_market_portfolio import GLOBAL_MARKET_PORTFOLIO, portfolio_counts
from global_market_source_contracts import SOURCE_CONTRACTS
from market_scope_registry import SHARED_FAMILIES
from source_registry import SOURCES

CountryState = Literal[
    "DISCOVERED", "RESEARCHING", "LEGAL_UNKNOWN", "LEGAL_BLOCKED",
    "TECHNICAL_UNKNOWN", "TECHNICAL_BLOCKED", "COMMERCIAL_UNKNOWN",
    "BUILD_CANDIDATE", "SHARED_CANDIDATE", "HOLD", "REMOVE",
    "IMPLEMENTING", "IMPLEMENTED_CANDIDATE", "INTEGRATION_PENDING",
    "GOLDEN_PENDING", "ACTIVE_PROVEN", "REVALIDATION_REQUIRED",
]
LegalState = Literal[
    "LEGAL_GREEN", "LEGAL_AMBER", "LEGAL_RED", "LEGAL_UNKNOWN",
    "HUMAN_LEGAL_REVIEW_REQUIRED",
]
EvidenceState = Literal["PROVEN", "PARTIAL", "UNKNOWN", "BLOCKED", "NOT_APPLICABLE"]
PriorityAClass = Literal[
    "NO_CODE", "SCAFFOLD", "PARTIAL_CONNECTOR", "CONNECTOR_GREEN",
    "LIVE_CONTRACT_UNKNOWN", "LEGAL_UNKNOWN", "INTEGRATION_PENDING",
    "ACTIVE_PROVEN",
]


@dataclass(frozen=True)
class LegalEvidence:
    country: str
    authority: str
    source_name: str
    official_domain: str
    source_type: str
    legal_owner: str
    terms_url: str
    license_url: str
    open_data_policy: str
    license_type: str
    commercial_reuse: EvidenceState
    redistribution: EvidenceState
    attribution: str
    derivative_use: EvidenceState
    database_rights: EvidenceState
    api_terms: str
    rate_limit_terms: str
    robots_relevance: str
    personal_data_presence: EvidenceState
    data_retention_restrictions: str
    geographic_restrictions: str
    credential_requirements: str
    evidence_date: str
    evidence_fingerprint: str
    fingerprint_scope: str
    last_verified: str
    next_review: str
    classification: LegalState
    interpretation: str


@dataclass(frozen=True)
class SharedCoverageAudit:
    country: str
    family: str
    market_config: EvidenceState
    country_mapping: EvidenceState
    source_family_eligibility: EvidenceState
    legal_evidence: EvidenceState
    taxonomy_handling: EvidenceState
    country_identification: EvidenceState
    tests: EvidenceState
    health_representation: EvidenceState
    operational_state: CountryState
    exact_gap: str


@dataclass(frozen=True)
class HoldMonitor:
    country: str
    reopen_trigger: str
    monitor_query: str
    official_authorities: tuple[str, ...]
    last_result: str
    last_checked: str
    next_check: str
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    monitoring_method: str


@dataclass(frozen=True)
class DiscoveryCandidate:
    country: str
    state: CountryState
    evidence_ref: str
    owner_ref: str
    reason: str


@dataclass(frozen=True)
class PriorityAStatus:
    country: str
    classification: PriorityAClass
    source_id: str
    legal_state: LegalState
    canonical_code: EvidenceState
    candidate_code: EvidenceState
    exact_gap: str


def _fingerprint(*parts: str) -> str:
    """Fingerprint the captured evidence record, never pretend to hash remote bytes."""
    payload = "\n".join(str(part).strip() for part in parts)
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


def _legal(*, country, authority, source_name, official_domain, source_type,
           terms_url, license_url, open_data_policy, license_type,
           commercial_reuse, redistribution, attribution, derivative_use,
           database_rights, api_terms, rate_limit_terms, robots_relevance,
           personal_data_presence, data_retention_restrictions,
           geographic_restrictions, credential_requirements, classification,
           interpretation, next_review):
    evidence_date = "2026-08-26"
    return LegalEvidence(
        country=country,
        authority=authority,
        source_name=source_name,
        official_domain=official_domain,
        source_type=source_type,
        legal_owner="Factory captures evidence; qualified human legal review retains genuine ambiguity authority",
        terms_url=terms_url,
        license_url=license_url,
        open_data_policy=open_data_policy,
        license_type=license_type,
        commercial_reuse=commercial_reuse,
        redistribution=redistribution,
        attribution=attribution,
        derivative_use=derivative_use,
        database_rights=database_rights,
        api_terms=api_terms,
        rate_limit_terms=rate_limit_terms,
        robots_relevance=robots_relevance,
        personal_data_presence=personal_data_presence,
        data_retention_restrictions=data_retention_restrictions,
        geographic_restrictions=geographic_restrictions,
        credential_requirements=credential_requirements,
        evidence_date=evidence_date,
        evidence_fingerprint=_fingerprint(
            country, source_name, terms_url, license_url, open_data_policy,
            license_type, commercial_reuse, redistribution, derivative_use,
            database_rights, api_terms, evidence_date,
        ),
        fingerprint_scope="CAPTURED_EVIDENCE_RECORD_NOT_REMOTE_PAGE_BYTES",
        last_verified=evidence_date,
        next_review=next_review,
        classification=classification,
        interpretation=interpretation,
    )


LEGAL_EVIDENCE = MappingProxyType({
    "Canada": _legal(
        country="Canada",
        authority="Public Services and Procurement Canada / Government of Canada Open Government",
        source_name="CanadaBuys tender notices",
        official_domain="open.canada.ca",
        source_type="official open-data CSV dataset",
        terms_url="https://open.canada.ca/en/open-government-licence-canada",
        license_url="https://open.canada.ca/en/open-government-licence-canada",
        open_data_policy="CanadaBuys tender notices are published through the official Open Government data portal.",
        license_type="Open Government Licence - Canada",
        commercial_reuse="PROVEN",
        redistribution="PROVEN",
        attribution="Required by the Open Government Licence - Canada.",
        derivative_use="PROVEN",
        database_rights="PARTIAL",
        api_terms="Baseline connector consumes official published CSV files, not site scraping.",
        rate_limit_terms="NOT_APPLICABLE to static published CSV snapshots; normal transport politeness remains required.",
        robots_relevance="NOT_APPLICABLE to official data-file URLs.",
        personal_data_presence="PARTIAL",
        data_retention_restrictions="No source-specific retention restriction captured; Privacy authority remains separate.",
        geographic_restrictions="None captured.",
        credential_requirements="None for published tender-notice CSV files.",
        classification="LEGAL_GREEN",
        interpretation="Commercial use, modification and distribution are explicitly licensed with attribution for this dataset; privacy/third-party rights remain separate.",
        next_review="2026-09-26",
    ),
    "United States": _legal(
        country="United States",
        authority="U.S. General Services Administration",
        source_name="SAM.gov Contract Opportunities public data services",
        official_domain="sam.gov",
        source_type="official public extract / public API",
        terms_url="https://sam.gov/about/terms-of-use",
        license_url="",
        open_data_policy="SAM.gov provides official public Contract Opportunities APIs/extracts and permits public sharing only from public API surfaces.",
        license_type="Public-data access terms; no explicit commercial-use licence captured for the exact bulk extract",
        commercial_reuse="UNKNOWN",
        redistribution="PROVEN",
        attribution="Preserve SAM.gov/GSA provenance; no source-specific attribution sentence captured for the bulk extract.",
        derivative_use="UNKNOWN",
        database_rights="NOT_APPLICABLE",
        api_terms="Use public APIs/extracts only. Sensitive/FOUO data cannot be publicly disseminated.",
        rate_limit_terms="Endpoint-specific; baseline connector uses the official public bulk extract.",
        robots_relevance="Automated page scraping is prohibited; APIs/extracts are the sanctioned automation boundary.",
        personal_data_presence="PARTIAL",
        data_retention_restrictions="No public-extract retention rule captured; sensitive-data rules remain excluded from this source slice.",
        geographic_restrictions="None captured for the public Contract Opportunities surface.",
        credential_requirements="Baseline public bulk-extract connector does not require a key.",
        classification="LEGAL_AMBER",
        interpretation="Public redistribution is evidenced, but explicit commercial reuse/derivative permission for the exact bulk extract was not located; UNKNOWN must not be inferred GREEN.",
        next_review="2026-09-02",
    ),
    "Chile": _legal(
        country="Chile",
        authority="Dirección de Compras y Contratación Pública (ChileCompra)",
        source_name="Mercado Público public procurement-process information",
        official_domain="chilecompra.cl",
        source_type="official procurement platform + official API/open-data surfaces",
        terms_url="https://www.chilecompra.cl/terminos-y-condiciones-de-uso/",
        license_url="",
        open_data_policy="ChileCompra states that procurement-procedure information is public and public access/use is unrestricted; Datos Abiertos supports reuse in reports/apps.",
        license_type="Public-information reuse terms; protected personal/reserved data excluded",
        commercial_reuse="PROVEN",
        redistribution="PROVEN",
        attribution="Preserve ChileCompra source provenance; ChileCompra reports/studies require source mention on republication.",
        derivative_use="PROVEN",
        database_rights="PARTIAL",
        api_terms="Canonical live API path requires a legitimate individual ticket.",
        rate_limit_terms="Respect publisher 429 behavior and bounded sequential access.",
        robots_relevance="Use official API/open-data interfaces; do not automate transactional UI.",
        personal_data_presence="PROVEN",
        data_retention_restrictions="Personal data has separate legal restrictions and cannot be treated as unrestricted process data.",
        geographic_restrictions="None captured for public procurement-process information.",
        credential_requirements="Real individual MERCADOPUBLICO_TICKET required for canonical live API proof.",
        classification="LEGAL_GREEN",
        interpretation="GREEN applies only to public procurement-process information; protected personal/reserved data stays outside this conclusion.",
        next_review="2026-09-26",
    ),
    "Brazil": _legal(
        country="Brazil",
        authority="Portal Nacional de Contratações Públicas (PNCP)",
        source_name="PNCP Dados Abertos / PCA API",
        official_domain="gov.br/pncp",
        source_type="official procurement open-data API",
        terms_url="https://www.gov.br/pncp/pt-br/acesso-a-informacao/dados-abertos",
        license_url="",
        open_data_policy="PNCP documents no-login public APIs and downloading/manipulating procurement data in applications.",
        license_type="Exact dataset commercial redistribution/derivative licence linkage not captured",
        commercial_reuse="PARTIAL",
        redistribution="UNKNOWN",
        attribution="UNKNOWN",
        derivative_use="UNKNOWN",
        database_rights="UNKNOWN",
        api_terms="Public query access is documented; production PCA update route behavior is still unstable in bounded probes.",
        rate_limit_terms="UNKNOWN",
        robots_relevance="Official API only; no scraping fallback authorized.",
        personal_data_presence="PARTIAL",
        data_retention_restrictions="UNKNOWN",
        geographic_restrictions="None captured.",
        credential_requirements="No login for documented public query access.",
        classification="LEGAL_AMBER",
        interpretation="Public API access/manipulation is proven, but commercial redistribution/derivative/database-rights certainty is not; do not promote to GREEN by inference.",
        next_review="2026-09-02",
    ),
})


PRIORITY_A = MappingProxyType({
    "Brazil": PriorityAStatus(
        "Brazil", "PARTIAL_CONNECTOR", "PNCP/PCA candidate", "LEGAL_AMBER",
        "UNKNOWN", "PROVEN",
        "Canonical main has no PNCP connector/source registration, but open PR #140 contains brazil_pncp_pca.py, brazil_runtime.py and deterministic tests. Candidate is not canonical and live PCA update contract remains blocked.",
    ),
    "Canada": PriorityAStatus(
        "Canada", "CONNECTOR_GREEN", "CA_CANADABUYS", "LEGAL_GREEN",
        "PROVEN", "PROVEN",
        "Merged connector + exact-head/live source proof exist; Factory Integration + Golden + product-country proof remain.",
    ),
    "United States": PriorityAStatus(
        "United States", "CONNECTOR_GREEN", "US_SAM", "LEGAL_AMBER",
        "PROVEN", "PROVEN",
        "Merged connector + live public-bulk proof exist; source_registry legal GREEN now conflicts with fresh Factory AMBER and is routed in issue #520. Integration/Golden remain separate.",
    ),
    "Chile": PriorityAStatus(
        "Chile", "LIVE_CONTRACT_UNKNOWN", "CL_MERCADOPUBLICO", "LEGAL_GREEN",
        "PROVEN", "PROVEN",
        "Merged deterministic/test-ticket connector exists; canonical live API proof waits on a legitimate project ticket, while other Factory lanes continue.",
    ),
})


_TED_SHARED = set(SHARED_FAMILIES["TED_EFORMS"])
_FRESH_SHARED_LEGAL_GREEN = {"Ecuador", "Paraguay", "South Africa"}


def _shared_audit(country: str) -> SharedCoverageAudit:
    if country in _TED_SHARED:
        return SharedCoverageAudit(
            country, "TED/eForms", "PARTIAL", "PROVEN", "PROVEN", "PARTIAL",
            "PARTIAL", "PROVEN", "PARTIAL", "PARTIAL", "REVALIDATION_REQUIRED",
            "Central TED source is healthy and country is identifiable, but there is no complete per-country taxonomy/product test, country-scoped health and Golden coverage.",
        )
    if country in _FRESH_SHARED_LEGAL_GREEN:
        return SharedCoverageAudit(
            country, "OCDS/common family", "PROVEN", "PROVEN", "PROVEN", "PROVEN",
            "PARTIAL", "PROVEN", "PROVEN", "PARTIAL", "INTEGRATION_PENDING",
            "Fresh publisher-scoped reuse licence is proven; country Integration/Golden/customer proof and full coverage semantics remain separate.",
        )
    if country == "Uruguay":
        return SharedCoverageAudit(
            country, "OCDS/common family with documented unique transport", "PROVEN", "PROVEN", "PARTIAL", "PARTIAL",
            "PARTIAL", "PROVEN", "PROVEN", "PARTIAL", "INTEGRATION_PENDING",
            "UY_ARCE is implemented via unique RSS + Record/Release transport; open-data licence is proven for ARCE datasets but exact live-transport linkage remains AMBER.",
        )
    if country == "Dominican Republic":
        return SharedCoverageAudit(
            country, "OCDS/common family", "PARTIAL", "PROVEN", "PARTIAL", "PARTIAL",
            "PARTIAL", "PROVEN", "PARTIAL", "PARTIAL", "INTEGRATION_PENDING",
            "Implementation belongs to existing owner PRs; sustainable discovery/detail completeness/economics and canonical composition remain.",
        )
    if country in {"Peru", "Guatemala"}:
        return SharedCoverageAudit(
            country, "OCDS/common family", "UNKNOWN", "PROVEN", "PARTIAL", "PARTIAL",
            "UNKNOWN", "PROVEN", "UNKNOWN", "UNKNOWN", "TECHNICAL_BLOCKED",
            "Official OCDS evidence exists but normal permitted hosted-machine access is blocked; no bypass is authorized.",
        )
    if country == "Honduras":
        return SharedCoverageAudit(
            country, "OCDS/common family", "UNKNOWN", "PROVEN", "PARTIAL", "PROVEN",
            "UNKNOWN", "PROVEN", "UNKNOWN", "UNKNOWN", "TECHNICAL_BLOCKED",
            "Rights/schema evidence is strong; one clean secure/current Release/Record/Files live paging proof is still missing.",
        )
    raise KeyError(f"not a canonical SHARED market: {country}")


SHARED_COVERAGE_AUDIT = MappingProxyType({
    country: _shared_audit(country)
    for countries in SHARED_FAMILIES.values()
    for country in countries
})


_HOLD_AUTHORITIES = {
    "Algeria": ("official Algerian public procurement authority",),
    "Angola": ("Serviço Nacional da Contratação Pública",),
    "Argentina": ("CONTRAT.AR / Oficina Nacional de Contrataciones",),
    "Australia": ("AusTender / Department of Finance",),
    "Côte d’Ivoire": ("Autorité Nationale de Régulation des Marchés Publics",),
    "DRC": ("Autorité de Régulation des Marchés Publics",),
    "Egypt": ("Egyptian Government Procurement Portal",),
    "Ethiopia": ("Public Procurement and Property Authority / e-GP",),
    "India": ("Government e-Marketplace / Central Public Procurement Portal",),
    "Indonesia": ("LKPP / INAPROC",),
    "Japan": ("Government Electronic Procurement System",),
    "Kenya": ("Public Procurement Regulatory Authority / e-GP",),
    "Mexico": ("ComprasMX / Secretaría Anticorrupción y Buen Gobierno",),
    "Morocco": ("Portail Marocain des Marchés Publics",),
    "New Zealand": ("New Zealand Government Procurement / GETS",),
    "Nigeria": ("Bureau of Public Procurement / NOCOPO",),
    "Panama": ("PanamaCompra / Dirección General de Contrataciones Públicas",),
    "Philippines": ("PhilGEPS",),
    "Rwanda": ("Rwanda Public Procurement Authority / UMUCYO",),
    "Saudi Arabia": ("Etimad / Ministry of Finance",),
    "Singapore": ("GeBIZ / Ministry of Finance",),
    "South Korea": ("KONEPS / Public Procurement Service / data.go.kr",),
    "Taiwan": ("Public Construction Commission / Government e-Procurement System",),
    "Ukraine": ("Prozorro / Ministry of Economy",),
    "United Arab Emirates": ("Ministry of Finance Digital Procurement Platform",),
    "Namibia": ("Central Procurement Board of Namibia / eProcurement",),
}

_HOLD_METHOD = {
    "South Korea": ("project_config_has:KONEPS_SERVICE_KEY AND official KONEPS source-contract fingerprint unchanged", "2026-09-02", "HIGH"),
    "Rwanda": ("official UMUCYO/OCDS licence or written commercial-reuse authorization changed", "2026-09-26", "HIGH"),
    "India": ("official broad live tender API/feed exists without CAPTCHA/manual-only access", "2026-09-26", "HIGH"),
    "Australia": ("AusTender official live ATM machine route + explicit reuse terms become available", "2026-09-26", "HIGH"),
    "Mexico": ("ComprasMX official stable live/incremental route + current API documentation", "2026-09-26", "HIGH"),
    "Namibia": ("official stable reusable machine route OR shared-adapter fit OR material customer demand", "2026-10-26", "MEDIUM"),
    "Ukraine": ("foreign-contractor operational/insurance execution-risk gate materially changes", "2026-09-26", "MEDIUM"),
}


def _hold_monitor(country: str) -> HoldMonitor:
    market = GLOBAL_MARKET_PORTFOLIO[country]
    query, next_check, confidence = _HOLD_METHOD.get(
        country,
        (f"{country}: official API/feed/reuse evidence satisfying current reconsideration trigger", "2026-09-26", "MEDIUM"),
    )
    return HoldMonitor(
        country, market.reconsideration_trigger, query, _HOLD_AUTHORITIES[country],
        "REOPEN_TRIGGER_NOT_PROVEN", "2026-08-26", next_check, confidence,
        "Targeted official-source query/fingerprint; full research reopens only after a material trigger change.",
    )


HOLD_MONITORS = MappingProxyType({
    country: _hold_monitor(country)
    for country, market in GLOBAL_MARKET_PORTFOLIO.items()
    if market.category == "HOLD"
})


DISCOVERY_CANDIDATES = MappingProxyType({
    "Turkey": DiscoveryCandidate("Turkey", "RESEARCHING", "TURKEY_EKAP_EVIDENCE.md", "PR #182", "EKAP national depth merits source/right/economics closure."),
    "Serbia": DiscoveryCandidate("Serbia", "RESEARCHING", "SERBIA_PROCUREMENT_EVIDENCE.md", "PR #182", "Official national portal merits source-contract/reuse closure."),
    "Georgia": DiscoveryCandidate("Georgia", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md", "PR #182", "Queued by Europe Frontier evidence cell."),
    "Albania": DiscoveryCandidate("Albania", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md", "PR #182", "Queued by Europe Frontier evidence cell."),
    "North Macedonia": DiscoveryCandidate("North Macedonia", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md", "PR #182", "Queued by Europe Frontier evidence cell."),
    "Moldova": DiscoveryCandidate("Moldova", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md", "PR #182", "Queued by Europe Frontier evidence cell."),
    "Bosnia and Herzegovina": DiscoveryCandidate("Bosnia and Herzegovina", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md", "PR #182", "Queued by Europe Frontier evidence cell."),
    "Montenegro": DiscoveryCandidate("Montenegro", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md", "PR #182", "Queued by Europe Frontier evidence cell."),
    "Qatar": DiscoveryCandidate("Qatar", "LEGAL_BLOCKED", "research/MENA_HIGH_VALUE_WAVE2_20260825.md", "PR #183/#235", "Ashghal technical slice exists, but current site terms conflict with commercial storage/redistribution absent written permission."),
    "Israel": DiscoveryCandidate("Israel", "LEGAL_UNKNOWN", "research/MENA_HIGH_VALUE_WAVE2_20260825.md", "PR #187/#235", "GPA construction slice exists; commercial reuse remains unresolved."),
    "Oman": DiscoveryCandidate("Oman", "LEGAL_UNKNOWN", "research/MENA_HIGH_VALUE_WAVE2_20260825.md", "PR #188/#235", "Esnad early-signal slice exists; reuse rights remain unresolved."),
    "Bahrain": DiscoveryCandidate("Bahrain", "LEGAL_UNKNOWN", "research/MENA_HIGH_VALUE_WAVE2_20260825.md", "PR #173", "Research identifies valuable lifecycle but explicit rights/legal review remains open; no production connector is authorized."),
    "Kuwait": DiscoveryCandidate("Kuwait", "LEGAL_UNKNOWN", "research/MENA_HIGH_VALUE_WAVE2_20260825.md", "PR #190/#235", "CAPT construction slice exists; reuse rights remain unresolved."),
})


OWNER_ROUTING_DEFECTS = MappingProxyType({
    "US_SAM_LEGAL_DRIFT": {
        "owner": "Sources / source-registry authority",
        "issue": "#520",
        "canonical_state": "source_registry.py advertises legal_reuse=GREEN",
        "factory_evidence": "LEGAL_AMBER: exact bulk commercial reuse/derivative permission not captured",
        "invariant": "LEGAL_UNKNOWN/AMBER != LEGAL_GREEN",
    },
})


def _canonical_operational_state(country: str) -> CountryState:
    market = GLOBAL_MARKET_PORTFOLIO[country]
    if market.category == "REMOVE":
        return "REMOVE"
    if market.category == "HOLD":
        return "HOLD"
    if market.category == "TECH_LAB":
        return "RESEARCHING"
    if country == "Brazil":
        return "TECHNICAL_BLOCKED"
    if country == "United States":
        return "LEGAL_UNKNOWN"
    if country == "Canada":
        return "INTEGRATION_PENDING"
    if country == "Chile":
        return "TECHNICAL_BLOCKED"
    if market.category == "SHARED":
        return SHARED_COVERAGE_AUDIT[country].operational_state
    if country in {"Portugal", "Spain", "France"}:
        return "REVALIDATION_REQUIRED"
    return "INTEGRATION_PENDING"


COUNTRY_OPERATIONAL_STATE = MappingProxyType({
    country: _canonical_operational_state(country)
    for country in GLOBAL_MARKET_PORTFOLIO
})


def dashboard_counts() -> dict[str, int]:
    """Return countable facts only; no fabricated percentages."""
    states = tuple(COUNTRY_OPERATIONAL_STATE.values())
    return {
        "TOTAL_JURISDICTIONS_DISCOVERED": len(GLOBAL_MARKET_PORTFOLIO) + len(DISCOVERY_CANDIDATES),
        "CANONICAL_PORTFOLIO_JURISDICTIONS": len(GLOBAL_MARKET_PORTFOLIO),
        "DISCOVERED_OUTSIDE_CANONICAL": len(DISCOVERY_CANDIDATES),
        "ACTIVE_PROVEN": states.count("ACTIVE_PROVEN"),
        "BUILD": portfolio_counts()["BUILD"],
        "SHARED": portfolio_counts()["SHARED"],
        "TECH_LAB": portfolio_counts()["TECH_LAB"],
        "IMPLEMENTING": states.count("IMPLEMENTING"),
        "INTEGRATION_PENDING": states.count("INTEGRATION_PENDING"),
        "GOLDEN_PENDING": states.count("GOLDEN_PENDING"),
        "HOLD": portfolio_counts()["HOLD"],
        "LEGAL_UNKNOWN": states.count("LEGAL_UNKNOWN"),
        "LEGAL_EVIDENCE_UNREVALIDATED": len(GLOBAL_MARKET_PORTFOLIO) - len(LEGAL_EVIDENCE),
        "TECHNICAL_UNKNOWN": states.count("TECHNICAL_UNKNOWN"),
        "TECHNICAL_BLOCKED": states.count("TECHNICAL_BLOCKED"),
        "REVALIDATION_REQUIRED": states.count("REVALIDATION_REQUIRED"),
        "REMOVE": portfolio_counts()["REMOVE"],
        "COUNTRIES_ADDED_LAST_7_DAYS": len(DISCOVERY_CANDIDATES),
    }


def legal_change_watch_targets() -> tuple[tuple[str, str, str, str], ...]:
    """Return source-scoped pages to fingerprint externally; no page hash is fabricated here."""
    rows = []
    for country, evidence in LEGAL_EVIDENCE.items():
        for kind, url in (("terms", evidence.terms_url), ("license", evidence.license_url)):
            if url:
                rows.append((country, kind, url, evidence.next_review))
    return tuple(sorted(set(rows)))


def active_proven_eligible(*, legal_green: bool, technical_source_green: bool,
                           identity_green: bool, pagination_green: bool,
                           restart_green: bool, lifecycle_green: bool,
                           temporal_green: bool, normalization_green: bool,
                           tenant_safe_green: bool, source_health_green: bool,
                           provenance_green: bool, integration_green: bool,
                           golden_green: bool) -> bool:
    return all((
        legal_green, technical_source_green, identity_green, pagination_green,
        restart_green, lifecycle_green, temporal_green, normalization_green,
        tenant_safe_green, source_health_green, provenance_green,
        integration_green, golden_green,
    ))


def validate_factory_registry() -> None:
    if portfolio_counts() != {"BUILD": 14, "SHARED": 31, "TECH_LAB": 3, "HOLD": 26, "REMOVE": 61}:
        raise RuntimeError("global portfolio drifted; revalidate Factory assumptions")
    if set(COUNTRY_OPERATIONAL_STATE) != set(GLOBAL_MARKET_PORTFOLIO):
        raise RuntimeError("operational registry must cover canonical portfolio exactly once")
    if len(SHARED_COVERAGE_AUDIT) != 31:
        raise RuntimeError("all 31 SHARED markets require an individual audit row")
    if set(HOLD_MONITORS) != {c for c, m in GLOBAL_MARKET_PORTFOLIO.items() if m.category == "HOLD"}:
        raise RuntimeError("every current HOLD market requires exactly one monitor")
    if any(not m.reopen_trigger or not m.monitor_query or not m.official_authorities for m in HOLD_MONITORS.values()):
        raise RuntimeError("HOLD monitors must be actionable")
    if set(DISCOVERY_CANDIDATES) & set(GLOBAL_MARKET_PORTFOLIO):
        raise RuntimeError("outside-canonical discovery cannot duplicate the 135 portfolio")
    if PRIORITY_A["Brazil"].classification != "PARTIAL_CONNECTOR":
        raise RuntimeError("Brazil open candidate code disappeared or classification drifted")
    if LEGAL_EVIDENCE["United States"].classification == "LEGAL_GREEN":
        raise RuntimeError("US commercial reuse must not be inferred GREEN without explicit evidence")
    if COUNTRY_OPERATIONAL_STATE["Brazil"] == "ACTIVE_PROVEN" or COUNTRY_OPERATIONAL_STATE["Chile"] == "ACTIVE_PROVEN":
        raise RuntimeError("blocked live source claims cannot be ACTIVE_PROVEN")
    if COUNTRY_OPERATIONAL_STATE["Canada"] == "ACTIVE_PROVEN":
        raise RuntimeError("connector/live green cannot bypass Integration + Golden")
    if SOURCES["CL_MERCADOPUBLICO"]["machine_access"] != "CREDENTIAL_REQUIRED":
        raise RuntimeError("Chile credential gate drifted")
    if "CA_CANADABUYS" not in SOURCES or "US_SAM" not in SOURCES:
        raise RuntimeError("validated Canada/US source entries disappeared")
    if set(SOURCE_CONTRACTS) != {"Brazil", "Canada", "United States", "Chile"}:
        raise RuntimeError("single Priority-A technical source-contract authority drifted")
    if LEGAL_EVIDENCE["Brazil"].redistribution != "UNKNOWN":
        raise RuntimeError("Brazil legal ambiguity was silently widened")


validate_factory_registry()
