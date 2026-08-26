"""Operational registry for Global Market Expansion, Source Legality & Country Automation.

This module is an additive evidence/composition layer. It deliberately does not
replace:
- global_market_portfolio.py for strategic portfolio decisions;
- market_scope_registry.py for the legacy 135-country scope record;
- source_registry.py for source runtime/readiness metadata.

The governing invariant is fail-closed: strategic BUILD/SHARED, connector
existence, HTTP success, and historical legal GREEN are never enough to produce
ACTIVE_PROVEN in this registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Literal

from global_market_portfolio import GLOBAL_MARKET_PORTFOLIO, portfolio_counts
from market_scope_registry import SHARED_FAMILIES
from source_registry import SOURCES

CountryState = Literal[
    "DISCOVERED",
    "RESEARCHING",
    "LEGAL_UNKNOWN",
    "LEGAL_BLOCKED",
    "TECHNICAL_UNKNOWN",
    "TECHNICAL_BLOCKED",
    "COMMERCIAL_UNKNOWN",
    "BUILD_CANDIDATE",
    "SHARED_CANDIDATE",
    "HOLD",
    "REMOVE",
    "IMPLEMENTING",
    "IMPLEMENTED_CANDIDATE",
    "INTEGRATION_PENDING",
    "GOLDEN_PENDING",
    "ACTIVE_PROVEN",
    "REVALIDATION_REQUIRED",
]

LegalState = Literal[
    "LEGAL_GREEN",
    "LEGAL_AMBER",
    "LEGAL_RED",
    "LEGAL_UNKNOWN",
    "HUMAN_LEGAL_REVIEW_REQUIRED",
]

EvidenceState = Literal["PROVEN", "PARTIAL", "UNKNOWN", "BLOCKED", "NOT_APPLICABLE"]

PriorityAClass = Literal[
    "NO_CODE",
    "SCAFFOLD",
    "PARTIAL_CONNECTOR",
    "CONNECTOR_GREEN",
    "LIVE_CONTRACT_UNKNOWN",
    "LEGAL_UNKNOWN",
    "INTEGRATION_PENDING",
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
    evidence_file: str
    reason: str


@dataclass(frozen=True)
class PriorityAStatus:
    country: str
    classification: PriorityAClass
    source_id: str
    legal_state: LegalState
    exact_gap: str


def _fingerprint(*parts: str) -> str:
    payload = "\n".join(str(part).strip() for part in parts)
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


# Fresh official-source legal revalidation captured by this Factory. These
# records are intentionally source-scoped: a GREEN record does not legalize
# other datasets from the same portal.
LEGAL_EVIDENCE = MappingProxyType({
    "Canada": LegalEvidence(
        country="Canada",
        authority="Public Services and Procurement Canada / Government of Canada Open Government",
        source_name="CanadaBuys tender notices",
        official_domain="open.canada.ca",
        source_type="official open-data CSV dataset",
        legal_owner="Global Market Expansion Factory (evidence); qualified counsel retains ambiguity authority",
        terms_url="https://open.canada.ca/en/open-government-licence-canada",
        license_url="https://open.canada.ca/en/open-government-licence-canada",
        open_data_policy="Dataset metadata explicitly links CanadaBuys tender notices to the Open Government Licence - Canada.",
        license_type="Open Government Licence - Canada",
        commercial_reuse="PROVEN",
        redistribution="PROVEN",
        attribution="Required by the Open Government Licence - Canada.",
        derivative_use="PROVEN",
        database_rights="PARTIAL",
        api_terms="Baseline connector uses official published CSV data files, not restricted site scraping.",
        rate_limit_terms="NOT_APPLICABLE for the published snapshot files; transport politeness still applies.",
        robots_relevance="NOT_APPLICABLE to the official CSV data-file path.",
        personal_data_presence="PARTIAL",
        data_retention_restrictions="No source-specific retention restriction proven in the captured licence evidence; privacy obligations remain separate.",
        geographic_restrictions="None proven in the captured licence evidence.",
        credential_requirements="None for the published CanadaBuys tender-notice data files.",
        evidence_date="2026-08-26",
        evidence_fingerprint=_fingerprint(
            "CanadaBuys tender notices",
            "Open Government Licence - Canada",
            "commercial use/copy/modify/publish/adapt/distribute permitted with attribution",
            "2026-08-26",
        ),
        last_verified="2026-08-26",
        next_review="2026-09-26",
        classification="LEGAL_GREEN",
        interpretation="GREEN only for CanadaBuys tender-notice information covered by the linked Open Government Licence; privacy and third-party rights remain separate.",
    ),
    "United States": LegalEvidence(
        country="United States",
        authority="U.S. General Services Administration",
        source_name="SAM.gov Contract Opportunities public data services",
        official_domain="sam.gov",
        source_type="official public extract / public API",
        legal_owner="Global Market Expansion Factory (evidence); qualified counsel retains ambiguity authority",
        terms_url="https://sam.gov/about/terms-of-use",
        license_url="",
        open_data_policy="SAM.gov exposes Contract Opportunities through public Data Services and a public Opportunities API.",
        license_type="U.S. federal public-data terms; source-specific restrictions apply",
        commercial_reuse="PROVEN",
        redistribution="PROVEN",
        attribution="Preserve SAM.gov/GSA source provenance; no special attribution sentence captured for this exact public extract.",
        derivative_use="PARTIAL",
        database_rights="NOT_APPLICABLE",
        api_terms="Use public APIs/extracts only. Sensitive/FOUO API data must not be publicly disseminated.",
        rate_limit_terms="Public API rate terms are endpoint-specific; baseline production path uses the public bulk extract.",
        robots_relevance="Automated scraping of SAM.gov pages is prohibited; official APIs/extracts are the permitted automation boundary.",
        personal_data_presence="PARTIAL",
        data_retention_restrictions="No extra retention restriction captured for the public Contract Opportunities extract; sensitive API rules do not transfer to public extracts.",
        geographic_restrictions="None proven for public Contract Opportunities extracts.",
        credential_requirements="No API key required by the baseline public bulk-extract connector.",
        evidence_date="2026-08-26",
        evidence_fingerprint=_fingerprint(
            "SAM.gov Contract Opportunities",
            "public data services/public API",
            "public API data may be shared publicly; scraping prohibited; sensitive data excluded",
            "2026-08-26",
        ),
        last_verified="2026-08-26",
        next_review="2026-09-26",
        classification="LEGAL_GREEN",
        interpretation="GREEN is scoped to public Contract Opportunities extracts/public API fields only; sensitive/FOUO and restricted entity data are excluded.",
    ),
    "Chile": LegalEvidence(
        country="Chile",
        authority="Dirección de Compras y Contratación Pública (ChileCompra)",
        source_name="Mercado Público public procurement information / API",
        official_domain="chilecompra.cl",
        source_type="official procurement platform + public API",
        legal_owner="Global Market Expansion Factory (evidence); qualified counsel retains ambiguity authority",
        terms_url="https://www.chilecompra.cl/terminos-y-condiciones-de-uso/",
        license_url="",
        open_data_policy="ChileCompra states that public procurement-process information has unrestricted public access/use and that Datos Abiertos supports reuse in reports/apps.",
        license_type="Public-information reuse terms; personal/reserved information excluded",
        commercial_reuse="PROVEN",
        redistribution="PROVEN",
        attribution="Source attribution is required for ChileCompra reports/studies; preserve source attribution for product provenance.",
        derivative_use="PROVEN",
        database_rights="PARTIAL",
        api_terms="Public API exists; access request requires a legitimate individual ticket via the official API portal.",
        rate_limit_terms="Connector must respect publisher 429 behavior and bounded sequential access.",
        robots_relevance="Do not automate the transactional site; use official API/open-data interfaces.",
        personal_data_presence="PROVEN",
        data_retention_restrictions="Personal data is governed separately and may not be republished merely because procurement-process information is public.",
        geographic_restrictions="None proven for public procurement-process information.",
        credential_requirements="Real individual MERCADOPUBLICO_TICKET required for the canonical live API path.",
        evidence_date="2026-08-26",
        evidence_fingerprint=_fingerprint(
            "ChileCompra Mercado Publico",
            "public process information access/use unrestricted",
            "open-data reuse for reports/apps; personal data separately restricted",
            "2026-08-26",
        ),
        last_verified="2026-08-26",
        next_review="2026-09-26",
        classification="LEGAL_GREEN",
        interpretation="GREEN applies to public procurement-process information, not protected personal/reserved data; live API still has a credential gate.",
    ),
    "Brazil": LegalEvidence(
        country="Brazil",
        authority="Portal Nacional de Contratações Públicas (PNCP)",
        source_name="PNCP Dados Abertos / PCA API",
        official_domain="pncp.gov.br",
        source_type="official procurement open-data API",
        legal_owner="Global Market Expansion Factory (evidence); qualified counsel owns unresolved commercial-rights judgement",
        terms_url="https://www.gov.br/pncp/pt-br/acesso-a-informacao/dados-abertos",
        license_url="",
        open_data_policy="PNCP officially exposes open-data APIs without login and permits downloading/manipulating public procurement data in applications.",
        license_type="Exact dataset commercial redistribution/derivative licence linkage not yet captured",
        commercial_reuse="PARTIAL",
        redistribution="UNKNOWN",
        attribution="UNKNOWN",
        derivative_use="UNKNOWN",
        database_rights="UNKNOWN",
        api_terms="Public query access is documented; production route behavior remains unstable in bounded probes.",
        rate_limit_terms="UNKNOWN",
        robots_relevance="Use official API only; no scraping fallback is authorized.",
        personal_data_presence="PARTIAL",
        data_retention_restrictions="UNKNOWN",
        geographic_restrictions="None proven.",
        credential_requirements="No login required for documented public query access.",
        evidence_date="2026-08-26",
        evidence_fingerprint=_fingerprint(
            "PNCP Dados Abertos",
            "public no-login API; download/manipulate in applications",
            "exact commercial redistribution/derivative licence remains unresolved",
            "2026-08-26",
        ),
        last_verified="2026-08-26",
        next_review="2026-09-02",
        classification="LEGAL_AMBER",
        interpretation="Do not promote to production on public accessibility alone; exact redistribution/derivative/database-rights evidence remains incomplete.",
    ),
})


PRIORITY_A = MappingProxyType({
    "Brazil": PriorityAStatus(
        country="Brazil",
        classification="PARTIAL_CONNECTOR",
        source_id="PNCP/PCA candidate (not registered in source_registry)",
        legal_state="LEGAL_AMBER",
        exact_gap="Prebuilt connector/tests exist, but current main has no PNCP source registration and the global PCA update route lacks stable live JSON/empty/paging semantics.",
    ),
    "Canada": PriorityAStatus(
        country="Canada",
        classification="INTEGRATION_PENDING",
        source_id="CA_CANADABUYS",
        legal_state="LEGAL_GREEN",
        exact_gap="Connector, deterministic CI and live production-path proof exist; Factory-specific Integration + Golden + per-country product coverage proof is not yet recorded.",
    ),
    "United States": PriorityAStatus(
        country="United States",
        classification="INTEGRATION_PENDING",
        source_id="US_SAM",
        legal_state="LEGAL_GREEN",
        exact_gap="Connector, deterministic CI and live public-bulk proof exist; Factory-specific Integration + Golden + customer-path proof is not yet recorded.",
    ),
    "Chile": PriorityAStatus(
        country="Chile",
        classification="LIVE_CONTRACT_UNKNOWN",
        source_id="CL_MERCADOPUBLICO",
        legal_state="LEGAL_GREEN",
        exact_gap="Connector is deterministic/test-ticket validated, but canonical live API proof requires a legitimate MERCADOPUBLICO_TICKET.",
    ),
})


_TED_SHARED = set(SHARED_FAMILIES["TED_EFORMS"])
_OCDS_SHARED = set(SHARED_FAMILIES["OCDS_API_BULK"])


def _shared_audit(country: str) -> SharedCoverageAudit:
    if country in _TED_SHARED:
        return SharedCoverageAudit(
            country=country,
            family="TED/eForms",
            market_config="PARTIAL",
            country_mapping="PROVEN",
            source_family_eligibility="PROVEN",
            legal_evidence="PARTIAL",
            taxonomy_handling="PARTIAL",
            country_identification="PROVEN",
            tests="PARTIAL",
            health_representation="PARTIAL",
            operational_state="REVALIDATION_REQUIRED",
            exact_gap="Central TED baseline exists, but Factory-specific country-level legal fingerprint, taxonomy/product-coverage test and country health evidence are not all individually proven.",
        )
    if country in {"Ecuador", "Paraguay", "South Africa", "Uruguay"}:
        return SharedCoverageAudit(
            country=country,
            family="OCDS/common family",
            market_config="PROVEN",
            country_mapping="PROVEN",
            source_family_eligibility="PROVEN",
            legal_evidence="PARTIAL",
            taxonomy_handling="PARTIAL",
            country_identification="PROVEN",
            tests="PROVEN",
            health_representation="PARTIAL",
            operational_state="INTEGRATION_PENDING",
            exact_gap="Implemented/ready source path exists; country-specific legal revalidation plus Integration/Golden/customer-path evidence remain.",
        )
    if country == "Dominican Republic":
        return SharedCoverageAudit(
            country=country,
            family="OCDS/common family",
            market_config="PARTIAL",
            country_mapping="PROVEN",
            source_family_eligibility="PROVEN",
            legal_evidence="PARTIAL",
            taxonomy_handling="PARTIAL",
            country_identification="PROVEN",
            tests="PARTIAL",
            health_representation="PARTIAL",
            operational_state="INTEGRATION_PENDING",
            exact_gap="Implementation belongs to existing owner PRs; sustainable discovery/detail completeness and composition remain integration work.",
        )
    if country in {"Peru", "Guatemala"}:
        return SharedCoverageAudit(
            country=country,
            family="OCDS/common family",
            market_config="UNKNOWN",
            country_mapping="PROVEN",
            source_family_eligibility="PARTIAL",
            legal_evidence="PARTIAL",
            taxonomy_handling="UNKNOWN",
            country_identification="PROVEN",
            tests="UNKNOWN",
            health_representation="UNKNOWN",
            operational_state="TECHNICAL_BLOCKED",
            exact_gap="Official OCDS evidence exists but normal permitted machine access is blocked in the current hosted environment; no bypass is authorized.",
        )
    if country == "Honduras":
        return SharedCoverageAudit(
            country=country,
            family="OCDS/common family",
            market_config="UNKNOWN",
            country_mapping="PROVEN",
            source_family_eligibility="PARTIAL",
            legal_evidence="PROVEN",
            taxonomy_handling="UNKNOWN",
            country_identification="PROVEN",
            tests="UNKNOWN",
            health_representation="UNKNOWN",
            operational_state="TECHNICAL_BLOCKED",
            exact_gap="Rights/schema evidence is strong; one clean secure/current live endpoint + paging proof is still missing.",
        )
    raise KeyError(f"not a canonical SHARED market: {country}")


SHARED_COVERAGE_AUDIT = MappingProxyType({
    country: _shared_audit(country)
    for countries in SHARED_FAMILIES.values()
    for country in countries
})


# These are vNext HOLD markets (26), not the older 28-count legacy view.
# Uganda/Tanzania/Zambia are TECH_LAB in vNext; Namibia is HOLD.
_HOLD_AUTHORITIES = {
    "Algeria": ("Algerian public procurement authority / official government portal",),
    "Angola": ("Serviço Nacional da Contratação Pública / official government portal",),
    "Argentina": ("CONTRAT.AR / Oficina Nacional de Contrataciones",),
    "Australia": ("AusTender / Department of Finance",),
    "Côte d’Ivoire": ("Autorité Nationale de Régulation des Marchés Publics",),
    "DRC": ("Autorité de Régulation des Marchés Publics",),
    "Egypt": ("Egyptian Government Procurement Portal",),
    "Ethiopia": ("Public Procurement and Property Authority / e-GP",),
    "India": ("Government e-Marketplace / Central Public Procurement Portal",),
    "Indonesia": ("LKPP / INAPROC",),
    "Japan": ("Government Electronic Procurement System / procurement authorities",),
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
    "South Korea": ("project_config_has:KONEPS_SERVICE_KEY AND official KONEPS API contract fingerprint unchanged", "2026-09-02", "HIGH"),
    "Rwanda": ("official UMUCYO/OCDS licence or written commercial-reuse authorization changed", "2026-09-26", "HIGH"),
    "India": ("official broad live tender API/feed published without CAPTCHA/manual-only access", "2026-09-26", "HIGH"),
    "Australia": ("AusTender official live ATM machine route + explicit reuse terms become available", "2026-09-26", "HIGH"),
    "Mexico": ("ComprasMX official stable live/incremental route + current API documentation", "2026-09-26", "HIGH"),
    "Namibia": ("official stable reusable machine route OR shared-adapter compatibility OR material customer demand", "2026-10-26", "MEDIUM"),
    "Ukraine": ("operational/insurance execution-risk gate materially changes for foreign contractors", "2026-09-26", "MEDIUM"),
}


def _hold_monitor(country: str) -> HoldMonitor:
    market = GLOBAL_MARKET_PORTFOLIO[country]
    query, next_check, confidence = _HOLD_METHOD.get(
        country,
        (
            f"{country}: official procurement authority API/feed/reuse terms matching reopen condition",
            "2026-09-26",
            "MEDIUM",
        ),
    )
    return HoldMonitor(
        country=country,
        reopen_trigger=market.reconsideration_trigger,
        monitor_query=query,
        official_authorities=_HOLD_AUTHORITIES[country],
        last_result="REOPEN_TRIGGER_NOT_PROVEN",
        last_checked="2026-08-26",
        next_check=next_check,
        confidence=confidence,
        monitoring_method="Targeted official-source fingerprint/query; full research reopens only on material trigger change.",
    )


HOLD_MONITORS = MappingProxyType({
    country: _hold_monitor(country)
    for country, market in GLOBAL_MARKET_PORTFOLIO.items()
    if market.category == "HOLD"
})


DISCOVERY_CANDIDATES = MappingProxyType({
    "Turkey": DiscoveryCandidate(
        "Turkey", "RESEARCHING", "TURKEY_EKAP_EVIDENCE.md",
        "Outside the canonical 135; EKAP may add national depth beyond TED but machine route, rights, identity and economics are not closed.",
    ),
    "Serbia": DiscoveryCandidate(
        "Serbia", "RESEARCHING", "SERBIA_PROCUREMENT_EVIDENCE.md",
        "Outside the canonical 135; official national portal may expose plans plus lifecycle, but source contract and reuse rights remain unproven.",
    ),
    "Georgia": DiscoveryCandidate(
        "Georgia", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md",
        "Outside the canonical 135 and explicitly queued by the existing Europe Frontier research cell.",
    ),
    "Albania": DiscoveryCandidate(
        "Albania", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md",
        "Outside the canonical 135 and explicitly queued by the existing Europe Frontier research cell.",
    ),
    "North Macedonia": DiscoveryCandidate(
        "North Macedonia", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md",
        "Outside the canonical 135 and explicitly queued by the existing Europe Frontier research cell.",
    ),
    "Moldova": DiscoveryCandidate(
        "Moldova", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md",
        "Outside the canonical 135 and explicitly queued by the existing Europe Frontier research cell.",
    ),
    "Bosnia and Herzegovina": DiscoveryCandidate(
        "Bosnia and Herzegovina", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md",
        "Outside the canonical 135 and explicitly queued by the existing Europe Frontier research cell.",
    ),
    "Montenegro": DiscoveryCandidate(
        "Montenegro", "DISCOVERED", "EUROPE_FRONTIER_CELL_RESEARCH.md",
        "Outside the canonical 135 and explicitly queued by the existing Europe Frontier research cell.",
    ),
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
    if country in {"Canada", "United States"}:
        return "INTEGRATION_PENDING"
    if country == "Chile":
        return "TECHNICAL_BLOCKED"

    if market.category == "SHARED":
        return SHARED_COVERAGE_AUDIT[country].operational_state

    if country in {"Portugal", "Spain", "France"}:
        return "REVALIDATION_REQUIRED"

    # Remaining BUILD connectors are repository-ready/productizable in prior
    # evidence, but this Factory has not independently proved Integration+Golden.
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
        "ACTIVE_PROVEN": states.count("ACTIVE_PROVEN"),
        "BUILD": portfolio_counts()["BUILD"],
        "SHARED": portfolio_counts()["SHARED"],
        "IMPLEMENTING": states.count("IMPLEMENTING"),
        "INTEGRATION_PENDING": states.count("INTEGRATION_PENDING"),
        "GOLDEN_PENDING": states.count("GOLDEN_PENDING"),
        "HOLD": portfolio_counts()["HOLD"],
        "LEGAL_UNKNOWN": sum(
            1 for country in GLOBAL_MARKET_PORTFOLIO
            if country not in LEGAL_EVIDENCE
        ),
        "TECHNICAL_UNKNOWN": states.count("TECHNICAL_UNKNOWN"),
        "REVALIDATION_REQUIRED": states.count("REVALIDATION_REQUIRED"),
        "REMOVE": portfolio_counts()["REMOVE"],
        "DISCOVERED_OUTSIDE_CANONICAL": len(DISCOVERY_CANDIDATES),
    }


def active_proven_eligible(
    *,
    legal_green: bool,
    technical_source_green: bool,
    identity_green: bool,
    pagination_green: bool,
    restart_green: bool,
    lifecycle_green: bool,
    temporal_green: bool,
    normalization_green: bool,
    tenant_safe_green: bool,
    source_health_green: bool,
    provenance_green: bool,
    integration_green: bool,
    golden_green: bool,
) -> bool:
    """Single promotion predicate: every required proof must be affirmative."""
    return all((
        legal_green,
        technical_source_green,
        identity_green,
        pagination_green,
        restart_green,
        lifecycle_green,
        temporal_green,
        normalization_green,
        tenant_safe_green,
        source_health_green,
        provenance_green,
        integration_green,
        golden_green,
    ))


def validate_factory_registry() -> None:
    if portfolio_counts() != {"BUILD": 14, "SHARED": 31, "TECH_LAB": 3, "HOLD": 26, "REMOVE": 61}:
        raise RuntimeError("global portfolio drifted; revalidate Factory assumptions")
    if set(COUNTRY_OPERATIONAL_STATE) != set(GLOBAL_MARKET_PORTFOLIO):
        raise RuntimeError("operational registry does not cover canonical portfolio exactly once")
    if len(SHARED_COVERAGE_AUDIT) != 31:
        raise RuntimeError("all 31 SHARED markets must have an individual audit row")
    if set(HOLD_MONITORS) != {
        country for country, market in GLOBAL_MARKET_PORTFOLIO.items() if market.category == "HOLD"
    }:
        raise RuntimeError("every current HOLD market must have exactly one monitor")
    if any(not monitor.reopen_trigger or not monitor.monitor_query or not monitor.official_authorities
           for monitor in HOLD_MONITORS.values()):
        raise RuntimeError("HOLD monitors must be actionable")
    if set(DISCOVERY_CANDIDATES) & set(GLOBAL_MARKET_PORTFOLIO):
        raise RuntimeError("outside-canonical discovery candidates cannot duplicate the 135 portfolio")
    if COUNTRY_OPERATIONAL_STATE["Brazil"] == "ACTIVE_PROVEN":
        raise RuntimeError("Brazil cannot be active while PNCP live endpoint contract is unstable")
    if COUNTRY_OPERATIONAL_STATE["Chile"] == "ACTIVE_PROVEN":
        raise RuntimeError("Chile cannot be active without the legitimate production API credential/live proof")
    if COUNTRY_OPERATIONAL_STATE["Canada"] == "ACTIVE_PROVEN" or COUNTRY_OPERATIONAL_STATE["United States"] == "ACTIVE_PROVEN":
        raise RuntimeError("connector/live green cannot bypass Factory Integration + Golden evidence")
    for country in ("Canada", "United States", "Chile", "Brazil"):
        if country not in LEGAL_EVIDENCE:
            raise RuntimeError(f"Priority-A legal evidence missing: {country}")
    if SOURCES["CL_MERCADOPUBLICO"]["machine_access"] != "CREDENTIAL_REQUIRED":
        raise RuntimeError("Chile credential gate drifted")
    if "CA_CANADABUYS" not in SOURCES or "US_SAM" not in SOURCES:
        raise RuntimeError("validated Canada/US source registry entries disappeared")


validate_factory_registry()
