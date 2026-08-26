"""Fail-closed technical source contracts for Global Market Expansion.

This registry records what the repository and bounded live evidence actually
prove. It is intentionally independent from commercial BUILD/SHARED choices and
from legal approval. Unknown test dimensions remain UNKNOWN rather than being
inferred from HTTP success or connector existence.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

ProbeState = Literal["PROVEN", "UNKNOWN", "BLOCKED", "NOT_APPLICABLE"]
ContractState = Literal[
    "TECHNICAL_GREEN",
    "TECHNICAL_PARTIAL",
    "TECHNICAL_UNKNOWN",
    "TECHNICAL_BLOCKED",
]


@dataclass(frozen=True)
class SourceTestMatrix:
    normal: ProbeState
    empty: ProbeState
    partial: ProbeState
    malformed: ProbeState
    duplicate: ProbeState
    updated: ProbeState
    cancelled: ProbeState
    pagination: ProbeState
    restart: ProbeState
    cursor_boundary: ProbeState
    timezone: ProbeState
    unknown_field: ProbeState
    extra_field: ProbeState


@dataclass(frozen=True)
class TechnicalSourceContract:
    country: str
    source_id: str
    source_name: str
    official_authority: str
    access_method: str
    api_feed_bulk_family: str
    auth_requirement: str
    pagination: str
    incremental_cursor: str
    identity: str
    update_identity: str
    deletion_cancellation: str
    publication_time: str
    modification_time: str
    deadline_semantics: str
    timezone: str
    currency: str
    value: str
    taxonomy: str
    cpv_ocds_eforms_mapping: str
    document_links: str
    buyer: str
    location: str
    lifecycle: str
    freshness: str
    completeness: str
    rate_limit: str
    error_semantics: str
    partial_response_semantics: str
    retry_safety: str
    tests: SourceTestMatrix
    live_evidence: ProbeState
    contract_state: ContractState
    evidence_refs: tuple[str, ...]
    last_technical_check: str
    last_live_probe: str
    next_review: str
    exact_gap: str


CANADA = TechnicalSourceContract(
    country="Canada",
    source_id="CA_CANADABUYS",
    source_name="CanadaBuys tender notices",
    official_authority="Public Services and Procurement Canada",
    access_method="Official published CSV snapshots",
    api_feed_bulk_family="generic conditional bulk/snapshot",
    auth_requirement="None for published data files",
    pagination="NOT_APPLICABLE: publisher supplies snapshot files",
    incremental_cursor="ETag + Last-Modified for New/Open; tracked solicitation state for reconciliation",
    identity="solicitationNumber-numeroSollicitation",
    update_identity="Same solicitation identity; amendmentNumber/amendmentDate carry version evidence",
    deletion_cancellation="Missing from Open is not cancellation; Complete may prove Cancelled; elapsed deadline may prove non-actionable expiry",
    publication_time="publicationDate-datePublication",
    modification_time="amendmentDate-dateModification plus HTTP validators",
    deadline_semantics="tenderClosingDate-appelOffresDateCloture converted from publisher fixed UTC-05:00",
    timezone="Publisher documents fixed UTC-05:00 even during Canadian DST periods",
    currency="No tender currency field in tender-notice dataset; emit empty",
    value="No tender value field in tender-notice dataset; emit empty",
    taxonomy="Publisher procurement category *CNST; UNSPSC/GSIN preserved as evidence",
    cpv_ocds_eforms_mapping="No invented CPV/OCDS/eForms mapping; native CanadaBuys semantics remain authoritative",
    document_links="Notice URL when supplied; official CanadaBuys public site fallback",
    buyer="contracting entity name/address fields",
    location="regions of opportunity/delivery plus contracting-entity geography",
    lifecycle="Open / Expired / Cancelled with fail-closed disappearance handling",
    freshness="New Tender Notices intraday acceleration; Open Tender Notices current active snapshot",
    completeness="Open snapshot is authoritative for currently open notices, not proof of all historical/terminal state without Complete evidence",
    rate_limit="Snapshot transport; conditional validators avoid unnecessary downloads",
    error_semantics="Schema drift, invalid UTF-8, duplicate construction identity and empty HTTP-200 body fail closed",
    partial_response_semantics="A truncated/schema-incomplete snapshot is invalid; cursor must not be advanced on failed invariants",
    retry_safety="Conditional snapshot reads are idempotent; cursor advances only after valid parsing/reconciliation",
    tests=SourceTestMatrix(
        normal="PROVEN",
        empty="PROVEN",
        partial="PROVEN",
        malformed="PROVEN",
        duplicate="PROVEN",
        updated="PROVEN",
        cancelled="PROVEN",
        pagination="NOT_APPLICABLE",
        restart="PROVEN",
        cursor_boundary="PROVEN",
        timezone="PROVEN",
        unknown_field="UNKNOWN",
        extra_field="UNKNOWN",
    ),
    live_evidence="PROVEN",
    contract_state="TECHNICAL_GREEN",
    evidence_refs=("CANADABUYS_EVIDENCE.md", "test_canada_buys.py"),
    last_technical_check="2026-08-26",
    last_live_probe="2026-08-25",
    next_review="2026-09-02",
    exact_gap="Extra/unknown-column compatibility is not separately proven; current parser intentionally requires the exact known 67-column publisher schema.",
)


UNITED_STATES = TechnicalSourceContract(
    country="United States",
    source_id="US_SAM",
    source_name="SAM.gov Contract Opportunities full public extract",
    official_authority="U.S. General Services Administration",
    access_method="Official public full CSV extract",
    api_feed_bulk_family="generic conditional bulk/snapshot",
    auth_requirement="None for baseline public full extract; optional API v2 requires key but is not baseline",
    pagination="NOT_APPLICABLE: baseline is one public full extract",
    incremental_cursor="ETag + Last-Modified conditional GET",
    identity="NoticeId",
    update_identity="NoticeId remains canonical identity; solicitation number is preserved but not assumed globally unique",
    deletion_cancellation="Daily snapshot disappearance does not itself prove cancellation; archive/deadline/lifecycle evidence must be explicit",
    publication_time="PostedDate",
    modification_time="HTTP ETag/Last-Modified; source row fields retained where present",
    deadline_semantics="ResponseDeadLine from publisher; actionable status remains source/deadline driven",
    timezone="Publisher timestamp/offset as supplied; no local-time inference authorized",
    currency="No current tender currency inferred from Award$; emit empty",
    value="Award$ is award information and never current tender value; emit empty for tender value",
    taxonomy="Six-digit NAICS beginning 23 is the publisher-native construction gate",
    cpv_ocds_eforms_mapping="No invented CPV/OCDS/eForms mapping; NAICS remains native authority",
    document_links="SAM opportunity Link field",
    buyer="Department/Agency, Sub-Tier and Office",
    location="Place-of-performance city/state/country fields",
    lifecycle="Notice/base/archive type plus active/deadline evidence; disappearance alone is not terminal truth",
    freshness="Publisher full extract with ETag/Last-Modified; API v2 can be future accelerator only",
    completeness="Full public Contract Opportunities extract is broad federal coverage, not all U.S. state/local procurement",
    rate_limit="Bulk baseline minimizes request count; API-v2 limits are not inherited into no-key bulk path",
    error_semantics="Schema drift and missing NoticeId fail closed; HTTP errors propagate; malformed source cannot advance cursor",
    partial_response_semantics="CSV header mismatch is invalid; partial/truncated-file-specific recovery is not separately proven",
    retry_safety="Conditional GET is idempotent; unchanged 304 preserves cursor exactly",
    tests=SourceTestMatrix(
        normal="PROVEN",
        empty="UNKNOWN",
        partial="UNKNOWN",
        malformed="PROVEN",
        duplicate="UNKNOWN",
        updated="UNKNOWN",
        cancelled="UNKNOWN",
        pagination="NOT_APPLICABLE",
        restart="PROVEN",
        cursor_boundary="PROVEN",
        timezone="UNKNOWN",
        unknown_field="UNKNOWN",
        extra_field="UNKNOWN",
    ),
    live_evidence="PROVEN",
    contract_state="TECHNICAL_PARTIAL",
    evidence_refs=("US_SAM_EVIDENCE.md", "tests/test_us_sam.py"),
    last_technical_check="2026-08-26",
    last_live_probe="2026-08-25",
    next_review="2026-09-02",
    exact_gap="Production path is live-validated, but the permanent Factory matrix still lacks explicit deterministic proofs for empty/partial/duplicate/update/cancel/timezone/extra-field cases.",
)


CHILE = TechnicalSourceContract(
    country="Chile",
    source_id="CL_MERCADOPUBLICO",
    source_name="Mercado Público classic procurement API",
    official_authority="Dirección de Compras y Contratación Pública (ChileCompra)",
    access_method="Official JSON API",
    api_feed_bulk_family="generic REST + date/active discovery + detail resolution",
    auth_requirement="Legitimate individual MERCADOPUBLICO_TICKET; documentation ticket is test-only",
    pagination="Current selected discovery contract uses date/active query sets rather than a proven page cursor",
    incremental_cursor="seen_by_day + tracked tender identities; detail resolution for new/disappeared candidates",
    identity="CodigoExterno",
    update_identity="Same CodigoExterno across lifecycle/detail updates",
    deletion_cancellation="Disappeared tracked identities are resolved through detail and publisher CodigoEstado; absence alone is not terminal truth",
    publication_time="Fechas.FechaPublicacion",
    modification_time="No distinct authoritative modification timestamp proven in current Factory evidence",
    deadline_semantics="Fechas.FechaCierre; exact timezone contract requires further explicit evidence",
    timezone="UNKNOWN for permanent Factory promotion until source timezone semantics are explicitly proven",
    currency="Moneda only when amount is visible; otherwise empty with value",
    value="MontoEstimado only when VisibilidadMonto == 1; never infer hidden amount",
    taxonomy="Obras == 2 OR item UNSPSC segment 72; construction-material goods such as segment 30 are excluded",
    cpv_ocds_eforms_mapping="Native UNSPSC is preserved; no invented CPV/eForms equivalence",
    document_links="Publisher API/source links as available in normalized detail",
    buyer="Comprador organism/unit fields",
    location="Comprador comuna/region fields; do not infer project site when absent",
    lifecycle="5 published/open; 6 closed; 7 unsuccessful; 8 awarded; 18 revoked; 19 suspended",
    freshness="Daily-date discovery plus active-set reconciliation; monthly OCDS was rejected for current discovery freshness",
    completeness="Classic API produced broad active results in validation, but production completeness is unproven without a real ticket and full live gate",
    rate_limit="HTTP 429 / publisher code 10500 observed; sequential bounded exponential backoff required",
    error_semantics="Missing/test-only credential rejected by default; HTTP errors fail; 429 retries bounded without cursor advancement",
    partial_response_semantics="Partial/malformed JSON behavior is not yet explicitly proven in deterministic Factory coverage",
    retry_safety="Sequential idempotent GETs; retry on bounded rate-limit path without cursor advance",
    tests=SourceTestMatrix(
        normal="PROVEN",
        empty="PROVEN",
        partial="UNKNOWN",
        malformed="UNKNOWN",
        duplicate="UNKNOWN",
        updated="PROVEN",
        cancelled="PROVEN",
        pagination="NOT_APPLICABLE",
        restart="PROVEN",
        cursor_boundary="PROVEN",
        timezone="UNKNOWN",
        unknown_field="UNKNOWN",
        extra_field="UNKNOWN",
    ),
    live_evidence="BLOCKED",
    contract_state="TECHNICAL_BLOCKED",
    evidence_refs=("CHILE_MERCADOPUBLICO_EVIDENCE.md", "tests/test_chile_mercadopublico.py"),
    last_technical_check="2026-08-26",
    last_live_probe="2026-08-25 (documentation-ticket validation only; not production credential proof)",
    next_review="ON_CREDENTIAL_OR_2026-09-26",
    exact_gap="Production live gate requires a legitimate project credential; timezone and malformed/partial response contracts also remain explicit test gaps.",
)


BRAZIL = TechnicalSourceContract(
    country="Brazil",
    source_id="PNCP_PCA_CANDIDATE",
    source_name="PNCP Dados Abertos / PCA",
    official_authority="Portal Nacional de Contratações Públicas (PNCP)",
    access_method="Official public API candidate",
    api_feed_bulk_family="candidate REST API; architecture not approved until live contract stabilizes",
    auth_requirement="Documented public query access without login",
    pagination="Research previously proved national discovery pagination, but no canonical production connector exists",
    incremental_cursor="No canonical main cursor/checkpoint implementation",
    identity="Research evidence exists for publisher identifiers; canonical implementation contract absent",
    update_identity="Research evidence exists for update timestamp semantics; canonical implementation absent",
    deletion_cancellation="UNKNOWN for production implementation",
    publication_time="Research evidence exists but no canonical source contract implementation",
    modification_time="Research observed update semantics; production route remains unstable",
    deadline_semantics="UNKNOWN for production implementation",
    timezone="UNKNOWN for production implementation",
    currency="UNKNOWN for production implementation",
    value="UNKNOWN for production implementation",
    taxonomy="Research proved publisher-native Works admission; implementation absent on current main",
    cpv_ocds_eforms_mapping="UNKNOWN; no mapping may be inferred",
    document_links="UNKNOWN for production implementation",
    buyer="UNKNOWN for production implementation",
    location="UNKNOWN for production implementation",
    lifecycle="UNKNOWN for production implementation",
    freshness="Recent-first discovery was research-proven; PCA update route did not produce a stable production-usable live contract",
    completeness="UNKNOWN; empty/non-JSON/timeouts cannot be interpreted as zero market",
    rate_limit="UNKNOWN; bounded probes observed timeout/non-JSON behavior",
    error_semantics="Timeout/non-JSON/empty responses remain failures, never zero-opportunity success",
    partial_response_semantics="UNKNOWN",
    retry_safety="UNKNOWN until a stable route and canonical checkpoint contract exist",
    tests=SourceTestMatrix(
        normal="UNKNOWN",
        empty="UNKNOWN",
        partial="UNKNOWN",
        malformed="UNKNOWN",
        duplicate="UNKNOWN",
        updated="UNKNOWN",
        cancelled="UNKNOWN",
        pagination="UNKNOWN",
        restart="UNKNOWN",
        cursor_boundary="UNKNOWN",
        timezone="UNKNOWN",
        unknown_field="UNKNOWN",
        extra_field="UNKNOWN",
    ),
    live_evidence="BLOCKED",
    contract_state="TECHNICAL_BLOCKED",
    evidence_refs=("master_execution_queue.py:Q010_BR_PNCP_DISCOVERY/Q030_BR_PNCP_PCA", "historical PR #135"),
    last_technical_check="2026-08-26",
    last_live_probe="Historical bounded probes only; no stable production route on current main",
    next_review="2026-09-02",
    exact_gap="Canonical main has NO_CODE for PNCP and the intended live PCA update path has not established stable JSON/empty/paging/retry semantics.",
)


SOURCE_CONTRACTS = MappingProxyType({
    contract.country: contract
    for contract in (BRAZIL, CANADA, UNITED_STATES, CHILE)
})


def technical_promotion_eligible(contract: TechnicalSourceContract) -> bool:
    """A live-proven source is still blocked if required matrix dimensions are unknown."""
    required = (
        contract.tests.normal,
        contract.tests.empty,
        contract.tests.partial,
        contract.tests.malformed,
        contract.tests.duplicate,
        contract.tests.updated,
        contract.tests.cancelled,
        contract.tests.restart,
        contract.tests.cursor_boundary,
        contract.tests.timezone,
        contract.tests.unknown_field,
        contract.tests.extra_field,
    )
    return (
        contract.live_evidence == "PROVEN"
        and contract.contract_state == "TECHNICAL_GREEN"
        and all(state in {"PROVEN", "NOT_APPLICABLE"} for state in required)
    )


def validate_source_contracts() -> None:
    if set(SOURCE_CONTRACTS) != {"Brazil", "Canada", "United States", "Chile"}:
        raise RuntimeError("Priority-A source contract registry must cover all four lanes")
    if BRAZIL.contract_state != "TECHNICAL_BLOCKED" or BRAZIL.live_evidence != "BLOCKED":
        raise RuntimeError("Brazil must remain blocked until stable canonical code/live contract exists")
    if CHILE.contract_state != "TECHNICAL_BLOCKED" or CHILE.live_evidence != "BLOCKED":
        raise RuntimeError("Chile must remain blocked until legitimate credential live evidence exists")
    if UNITED_STATES.contract_state == "TECHNICAL_GREEN":
        raise RuntimeError("US cannot be Factory technical-green while explicit matrix gaps remain")
    if technical_promotion_eligible(CANADA):
        raise RuntimeError("Canada has explicit unknown extra/unknown-field behavior; do not fake full matrix green")
    if any(technical_promotion_eligible(contract) for contract in SOURCE_CONTRACTS.values()):
        raise RuntimeError("No Priority-A market has yet closed the entire permanent technical matrix")


validate_source_contracts()
