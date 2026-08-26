"""Publisher-scoped legal evidence for SHARED procurement sources.

OCDS is a data standard, not a universal data licence. Each publisher's selected
source slice must carry its own reuse evidence. A publisher legal GREEN never
implies complete national procurement coverage or Golden/product proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Literal

LegalState = Literal["LEGAL_GREEN", "LEGAL_AMBER", "LEGAL_RED", "LEGAL_UNKNOWN"]
EvidenceState = Literal["PROVEN", "PARTIAL", "UNKNOWN"]


@dataclass(frozen=True)
class SharedPublisherLegalEvidence:
    country: str
    source_id: str
    authority: str
    selected_source_slice: str
    official_urls: tuple[str, ...]
    licence: str
    commercial_reuse: EvidenceState
    redistribution: EvidenceState
    derivative_use: EvidenceState
    attribution: str
    exact_scope_limit: str
    classification: LegalState
    last_verified: str
    next_review: str
    semantic_fingerprint: str


def _fingerprint(*claims: str) -> str:
    return "sha256:" + sha256("\n".join(claims).encode("utf-8")).hexdigest()


def _evidence(*, country, source_id, authority, selected_source_slice,
              official_urls, licence, commercial_reuse, redistribution,
              derivative_use, attribution, exact_scope_limit, classification,
              next_review):
    claims = (
        country, source_id, selected_source_slice, licence, commercial_reuse,
        redistribution, derivative_use, attribution, exact_scope_limit,
        classification, "2026-08-26",
    )
    return SharedPublisherLegalEvidence(
        country=country,
        source_id=source_id,
        authority=authority,
        selected_source_slice=selected_source_slice,
        official_urls=tuple(official_urls),
        licence=licence,
        commercial_reuse=commercial_reuse,
        redistribution=redistribution,
        derivative_use=derivative_use,
        attribution=attribution,
        exact_scope_limit=exact_scope_limit,
        classification=classification,
        last_verified="2026-08-26",
        next_review=next_review,
        semantic_fingerprint=_fingerprint(*claims),
    )


ECUADOR = _evidence(
    country="Ecuador",
    source_id="EC_SERCOP",
    authority="Servicio Nacional de Contratación Pública (SERCOP)",
    selected_source_slice="Contrataciones Abiertas Ecuador OCDS API / record packages",
    official_urls=(
        "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos/api",
    ),
    licence="Creative Commons Attribution 3.0 Ecuador (embedded in official OCDS response)",
    commercial_reuse="PROVEN",
    redistribution="PROVEN",
    derivative_use="PROVEN",
    attribution="Required by CC BY 3.0 Ecuador; preserve SERCOP/OCDS provenance.",
    exact_scope_limit=(
        "GREEN is limited to the OCDS/open-data source carrying this licence. It is not proof of every Ecuadorian procurement source, document right, or personal-data use."
    ),
    classification="LEGAL_GREEN",
    next_review="2026-09-26",
)


PARAGUAY = _evidence(
    country="Paraguay",
    source_id="PY_DNCP",
    authority="Dirección Nacional de Contrataciones Públicas (DNCP)",
    selected_source_slice="DNCP Datos Abiertos API v3 / OCDS and published CSV data",
    official_urls=(
        "https://www.contrataciones.gov.py/datos/api/v3/doc",
        "https://www.contrataciones.gov.py/datos/data",
        "https://www.contrataciones.gov.py/datos/aviso-legal",
    ),
    licence="Creative Commons Attribution 4.0",
    commercial_reuse="PROVEN",
    redistribution="PROVEN",
    derivative_use="PROVEN",
    attribution="Required by CC BY 4.0; preserve DNCP/OCDS provenance.",
    exact_scope_limit=(
        "GREEN applies to the DNCP open-data/OCDS publication. OAuth/rate limits remain technical contracts; attached third-party documents are not silently relicensed."
    ),
    classification="LEGAL_GREEN",
    next_review="2026-09-26",
)


SOUTH_AFRICA = _evidence(
    country="South Africa",
    source_id="ZA_ETENDERS",
    authority="National Treasury",
    selected_source_slice="eTender Transparency Portal OCDS bulk downloads + JSON REST API",
    official_urls=(
        "https://data.etenders.gov.za/",
        "https://data-uat.etenders.gov.za/Home/LearnMore",
    ),
    licence="Creative Commons Attribution 4.0",
    commercial_reuse="PROVEN",
    redistribution="PROVEN",
    derivative_use="PROVEN",
    attribution="Required by CC BY 4.0; preserve National Treasury/eTender provenance.",
    exact_scope_limit=(
        "Publisher explicitly states the OCDS portal is a subset of public procurement data. LEGAL_GREEN does not mean complete South African market coverage."
    ),
    classification="LEGAL_GREEN",
    next_review="2026-09-26",
)


URUGUAY = _evidence(
    country="Uruguay",
    source_id="UY_ARCE",
    authority="Agencia Reguladora de Compras Estatales (ARCE)",
    selected_source_slice="current RSS + Record/Release transport used by UY_ARCE",
    official_urls=(
        "https://catalogodatos.gub.uy/dataset/arce-datos-historicos-de-compras",
        "https://www.gub.uy/agencia-reguladora-compras-estatales/datos-y-estadisticas/datos/licencia-datos-abiertos",
        "https://www.gub.uy/agencia-reguladora-compras-estatales/datos-y-estadisticas/datos/open-contracting",
    ),
    licence="Licencia de Datos Abiertos - Uruguay v0.1 is proven for ARCE open datasets; exact live-transport linkage not yet proven",
    commercial_reuse="PARTIAL",
    redistribution="PARTIAL",
    derivative_use="PARTIAL",
    attribution="Uruguay open-data licence requires provider, licence and dataset attribution plus modification notice.",
    exact_scope_limit=(
        "Commercial/open reuse is explicit for ARCE open data and historical OCDS. The Factory has not yet captured an official statement tying the exact current RSS + Record/Release transport to that licence; do not infer it."
    ),
    classification="LEGAL_AMBER",
    next_review="2026-09-02",
)


SHARED_PUBLISHER_LEGAL_EVIDENCE = MappingProxyType({
    row.country: row for row in (ECUADOR, PARAGUAY, SOUTH_AFRICA, URUGUAY)
})


def validate_shared_publisher_legal_evidence() -> None:
    if set(SHARED_PUBLISHER_LEGAL_EVIDENCE) != {"Ecuador", "Paraguay", "South Africa", "Uruguay"}:
        raise RuntimeError("publisher legal cell drifted")
    if any(
        SHARED_PUBLISHER_LEGAL_EVIDENCE[country].classification != "LEGAL_GREEN"
        for country in ("Ecuador", "Paraguay", "South Africa")
    ):
        raise RuntimeError("fresh explicit publisher licences unexpectedly lost GREEN")
    if URUGUAY.classification != "LEGAL_AMBER" or URUGUAY.commercial_reuse != "PARTIAL":
        raise RuntimeError("Uruguay live transport must remain fail-closed until exact licence linkage is proven")
    if "subset" not in SOUTH_AFRICA.exact_scope_limit:
        raise RuntimeError("South Africa legal green must not erase the publisher completeness caveat")
    if any(not row.semantic_fingerprint.startswith("sha256:") for row in SHARED_PUBLISHER_LEGAL_EVIDENCE.values()):
        raise RuntimeError("shared publisher legal evidence requires semantic fingerprints")


validate_shared_publisher_legal_evidence()
